import hashlib
import re
import struct

import pytest

from spingo_games_rng import (
    uniform32_from_hash,
    uniform32_float_from_hash,
    uniform52_from_hash,
    generate_server_seed,
    generate_client_seed,
    hash_seed,
)

# Stream/dieharder-feed helpers live under tests/ -- they are validation
# tooling, not part of the shipped package.
from _streams import (
    uint32_stream,
    uint52_stream,
    rotating_uint32_stream,
    rotating_uint52_stream,
    repack_to_uint32,
    write_binary_stream,
)

# Known-good reference values that lock the algorithm's output.
REFERENCE = {
    0: (3772253323, "e0d8048b"),
    1: (2296099867, "88dbb41b"),
    2: (3875600623, "e700f8ef"),
}


def test_matches_reference_values():
    for nonce, (r_int, hex8) in REFERENCE.items():
        got_int, got_hex = uniform32_from_hash("server", "client", nonce)
        assert got_int == r_int
        assert got_hex[:8] == hex8
        assert got_int == int(hex8, 16)


def test_deterministic():
    a = uniform32_from_hash("server", "client", 1)
    b = uniform32_from_hash("server", "client", 1)
    assert a == b


def test_range_is_uint32():
    for nonce in range(1000):
        r_int, _ = uniform32_from_hash("s", "c", nonce)
        assert 0 <= r_int < 2 ** 32


def test_float_in_unit_interval():
    for nonce in range(1000):
        r, _, r_int = uniform32_float_from_hash("s", "c", nonce)
        assert 0.0 <= r < 1.0
        assert r == r_int / 2 ** 32


def test_stream_matches_function():
    stream = list(uint32_stream("server", "client", start_nonce=0, count=3))
    expected = [REFERENCE[n][0] for n in (0, 1, 2)]
    assert stream == expected


def test_stream_respects_start_nonce():
    stream = list(uint32_stream("server", "client", start_nonce=2, count=1))
    assert stream == [REFERENCE[2][0]]


def test_write_binary_stream_big_endian(tmp_path):
    path = tmp_path / "out.bin"
    with open(path, "wb") as fh:
        n = write_binary_stream(fh, "server", "client", count=3)
    assert n == 3
    data = path.read_bytes()
    assert len(data) == 12
    words = struct.unpack(">III", data)
    assert list(words) == [REFERENCE[n][0] for n in (0, 1, 2)]


def test_generate_server_seed_default_is_40_hex_chars():
    seed = generate_server_seed()
    assert len(seed) == 40
    assert re.fullmatch(r"[0-9a-f]+", seed)


def test_generate_server_seed_honours_byte_length():
    assert len(generate_server_seed(8)) == 16  # 8 bytes -> 16 hex chars


def test_generate_client_seed_default_length_and_alphabet():
    seed = generate_client_seed()
    assert len(seed) == 20
    assert re.fullmatch(r"[A-Za-z0-9]+", seed)


def test_generate_client_seed_honours_length():
    assert len(generate_client_seed(32)) == 32


def test_seeds_are_random():
    assert generate_server_seed() != generate_server_seed()
    assert generate_client_seed() != generate_client_seed()


def test_hash_seed_is_sha256_hex():
    assert hash_seed("server") == hashlib.sha256(b"server").hexdigest()
    assert len(hash_seed("anything")) == 64


def test_generated_seeds_drive_the_rng():
    server, client = generate_server_seed(), generate_client_seed()
    r_int, digest = uniform32_from_hash(server, client, 0)
    assert 0 <= r_int < 2 ** 32
    assert r_int == int(digest[:8], 16)


def test_rotating_stream_count_and_range():
    words = list(rotating_uint32_stream("client", rotate_every=1, count=100))
    assert len(words) == 100
    assert all(0 <= w < 2 ** 32 for w in words)


def test_rotating_stream_uses_deterministic_factory():
    # A factory cycling through known seeds lets us predict the output: with
    # rotate_every=2 the nonce walks 0,1 within each seed.
    seeds = iter(["A", "B"])      # one value consumed per epoch (2 epochs)
    factory = lambda: next(seeds)  # noqa: E731
    words = list(rotating_uint32_stream("client", rotate_every=2, count=4, seed_factory=factory))
    expected = [
        uniform32_from_hash("A", "client", 0)[0],
        uniform32_from_hash("A", "client", 1)[0],
        uniform32_from_hash("B", "client", 0)[0],
        uniform32_from_hash("B", "client", 1)[0],
    ]
    assert words == expected


def test_rotating_every_one_changes_seed_each_word():
    # rotate_every=1 => nonce is always 0, the seed carries all the variation.
    seeds = iter(["s0", "s1", "s2"])
    words = list(rotating_uint32_stream("c", rotate_every=1, count=3, seed_factory=lambda: next(seeds)))
    expected = [uniform32_from_hash(s, "c", 0)[0] for s in ("s0", "s1", "s2")]
    assert words == expected


def test_rotating_stream_rejects_bad_rotate_every():
    with pytest.raises(ValueError):
        list(rotating_uint32_stream("c", rotate_every=0, count=1))


def test_uint52_stream_matches_function_and_range():
    stream = list(uint52_stream("server", "client", start_nonce=0, count=4))
    expected = [uniform52_from_hash("server", "client", n)[0] for n in range(4)]
    assert stream == expected
    assert all(0 <= w < 2 ** 52 for w in stream)


def test_repack_to_uint32_concatenates_bits():
    # Two 52-bit values -> their 104-bit concatenation -> three 32-bit words
    # (104 // 32 = 3, with 8 leftover bits dropped).
    vals = [0x000000000000F, (1 << 52) - 1]  # 13 hex digits each = 52 bits
    bits = "".join(format(v, "052b") for v in vals)
    expected = [int(bits[i:i + 32], 2) for i in range(0, len(bits) - 31, 32)]
    assert list(repack_to_uint32(vals, 52)) == expected
    assert len(expected) == 3  # 8 trailing bits dropped


def test_repack_output_is_uint32_and_deterministic():
    from itertools import islice
    src = lambda: islice(repack_to_uint32(uint52_stream("server", "client"), 52), 1000)
    a, b = list(src()), list(src())
    assert len(a) == 1000
    assert all(0 <= w < 2 ** 32 for w in a)
    assert a == b


def test_rotating_uint52_stream_count_and_range():
    words = list(rotating_uint52_stream("client", rotate_every=2, count=100))
    assert len(words) == 100
    assert all(0 <= w < 2 ** 52 for w in words)


def test_rotating_uint52_uses_deterministic_factory():
    seeds = iter(["A", "B"])
    factory = lambda: next(seeds)  # noqa: E731
    words = list(rotating_uint52_stream("client", rotate_every=2, count=4, seed_factory=factory))
    expected = [
        uniform52_from_hash("A", "client", 0)[0],
        uniform52_from_hash("A", "client", 1)[0],
        uniform52_from_hash("B", "client", 0)[0],
        uniform52_from_hash("B", "client", 1)[0],
    ]
    assert words == expected


def test_endianness_flips_bytes(tmp_path):
    be = tmp_path / "be.bin"
    le = tmp_path / "le.bin"
    with open(be, "wb") as fh:
        write_binary_stream(fh, "s", "c", count=4, big_endian=True)
    with open(le, "wb") as fh:
        write_binary_stream(fh, "s", "c", count=4, big_endian=False)
    be_words = struct.unpack(">IIII", be.read_bytes())
    le_words = struct.unpack("<IIII", le.read_bytes())
    assert be_words == le_words  # same logical values, just byte order differs
