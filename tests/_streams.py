"""Stream helpers that turn the HMAC RNG into 32-bit words for dieharder.

This is validation tooling, **not** part of the shipped library -- the package
itself is just the RNG primitives (``core``) and seed helpers (``seeds``). Both
the pytest suite and the dieharder feed script (``tests/dieharder_feed.py``)
import these.

The canonical mapping fixes ``server_seed`` and ``client_seed``, then walks
``nonce = start, start+1, ...`` emitting one draw per nonce. Each word is an
independent HMAC-SHA256 draw, so the stream is exactly the RNG under test -- no
extra mixing is applied. ``rotating_*`` variants instead draw a fresh server
seed every ``rotate_every`` words, as in the commit-reveal scheme.

dieharder reads 32-bit words, so the 52-bit (bustabit) draw is bit-packed into
a continuous 32-bit word stream via :func:`repack_to_uint32` -- every bit used
once, none wasted.
"""
import struct
from itertools import count as _count, islice
from typing import Callable, Iterable, Iterator, Optional

from spingo_games_rng import (
    generate_server_seed,
    uniform32_from_hash,
    uniform52_from_hash,
)

Draw = Callable[[str, str, int], "tuple[int, str]"]


def _draw_stream(draw: Draw, server_seed: str, client_seed: str,
                 start_nonce: int, count: Optional[int]) -> Iterator[int]:
    nonces = _count(start_nonce)
    if count is not None:
        nonces = islice(nonces, count)
    for nonce in nonces:
        r_int, _ = draw(server_seed, client_seed, nonce)
        yield r_int


def uint32_stream(server_seed: str, client_seed: str, start_nonce: int = 0,
                  count: Optional[int] = None) -> Iterator[int]:
    """Yield uint32 values, one per nonce, starting at ``start_nonce``.

    ``count=None`` makes the stream infinite (for piping into ``dieharder -a``).
    """
    return _draw_stream(uniform32_from_hash, server_seed, client_seed, start_nonce, count)


def uint52_stream(server_seed: str, client_seed: str, start_nonce: int = 0,
                  count: Optional[int] = None) -> Iterator[int]:
    """Yield uint52 values, one per nonce. The 52-bit counterpart of
    :func:`uint32_stream`; bit-pack with :func:`repack_to_uint32` for dieharder.
    """
    return _draw_stream(uniform52_from_hash, server_seed, client_seed, start_nonce, count)


def _rotating_stream(draw: Draw, client_seed: str, rotate_every: int,
                     count: Optional[int], seed_factory: Callable[[], str]) -> Iterator[int]:
    if rotate_every < 1:
        raise ValueError("rotate_every must be >= 1")

    def epochs() -> Iterator[int]:
        while True:
            server_seed = seed_factory()
            for nonce in range(rotate_every):
                r_int, _ = draw(server_seed, client_seed, nonce)
                yield r_int

    return epochs() if count is None else islice(epochs(), count)


def rotating_uint32_stream(client_seed: str, rotate_every: int = 1, count: Optional[int] = None,
                           seed_factory: Callable[[], str] = generate_server_seed) -> Iterator[int]:
    """Yield uint32 values while rotating the server seed.

    A fresh server seed is drawn from ``seed_factory`` every ``rotate_every``
    words; within each epoch the nonce walks ``0 .. rotate_every-1`` -- mirroring
    the commit-reveal scheme where the nonce is per server seed. ``rotate_every=1``
    changes the server seed every single word.

    By default ``seed_factory`` is ``generate_server_seed`` (``secrets``-random),
    so the stream is **not reproducible** between runs -- fine for dieharder. Pass
    a deterministic ``seed_factory`` if you need reproducibility.
    """
    return _rotating_stream(uniform32_from_hash, client_seed, rotate_every, count, seed_factory)


def rotating_uint52_stream(client_seed: str, rotate_every: int = 1, count: Optional[int] = None,
                           seed_factory: Callable[[], str] = generate_server_seed) -> Iterator[int]:
    """The 52-bit counterpart of :func:`rotating_uint32_stream`. Bit-pack with
    :func:`repack_to_uint32` for dieharder."""
    return _rotating_stream(uniform52_from_hash, client_seed, rotate_every, count, seed_factory)


def repack_to_uint32(values: Iterable[int], width: int) -> Iterator[int]:
    """Treat each value as ``width`` big-endian bits, concatenate them into one
    continuous bitstream, and yield successive 32-bit words.

    The statistically correct way to feed a non-32-bit source (e.g. the 52-bit
    draw) to dieharder: every bit is used exactly once. A trailing remainder of
    fewer than 32 bits is dropped.
    """
    mask = (1 << width) - 1
    buf = 0
    nbits = 0
    for v in values:
        buf = (buf << width) | (v & mask)
        nbits += width
        while nbits >= 32:
            nbits -= 32
            yield (buf >> nbits) & 0xFFFFFFFF
        buf &= (1 << nbits) - 1  # keep only the leftover low bits, stay bounded


def write_words(out, words: Iterable[int], big_endian: bool = True) -> int:
    """Write an iterable of uint32 words to a binary file object as raw 4-byte
    words. Returns the number written.

    This is the format dieharder expects from ``-g 200`` (stdin raw) and ``-g 201``
    (file raw). Byte order only permutes the bits inside each word, so it does not
    affect test verdicts; big-endian is the default to match the big-endian
    interpretation of the hex digest.
    """
    fmt = ">I" if big_endian else "<I"
    written = 0
    for r_int in words:
        out.write(struct.pack(fmt, r_int))
        written += 1
    return written


def write_binary_stream(out, server_seed: str, client_seed: str, start_nonce: int = 0,
                        count: Optional[int] = None, big_endian: bool = True) -> int:
    """Convenience: write the fixed-seed ``uint32_stream`` as raw words."""
    return write_words(out, uint32_stream(server_seed, client_seed, start_nonce, count), big_endian=big_endian)
