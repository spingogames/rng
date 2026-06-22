"""Emit a stream of RNG words so it can be piped into dieharder.

This is validation tooling that lives under ``tests/`` -- it is not part of the
installed package. Run it directly:

    python tests/dieharder_feed.py --server-seed s --client-seed c | dieharder -g 200 -a
    python tests/dieharder_feed.py -s s -c c --bits 52 | dieharder -g 200 -a
    python tests/dieharder_feed.py -c c --rotate-every 100 --bits 52 | dieharder -g 200 -a

Write a fixed number of words to a file, then test the file::

    python tests/dieharder_feed.py -s s -c c -n 50000000 -o stream.bin
    dieharder -g 201 -f stream.bin -a
"""
import argparse
import os
import sys
from itertools import islice

from _streams import (
    repack_to_uint32,
    rotating_uint32_stream,
    rotating_uint52_stream,
    uint32_stream,
    uint52_stream,
    write_words,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dieharder_feed",
        description="Emit a stream of RNG values for dieharder.",
    )
    p.add_argument("-s", "--server-seed", default=None,
                   help="server seed (HMAC key); required unless --rotate-every "
                        "is used, in which case server seeds are generated")
    p.add_argument("-c", "--client-seed", required=True,
                   help="client seed (part of the HMAC message)")
    p.add_argument("-n", "--count", type=int, default=None,
                   help="number of 32-bit words to emit (default: unbounded stream)")
    p.add_argument("--start-nonce", type=int, default=0,
                   help="first nonce in the sequence (default: 0); ignored when --rotate-every is set")
    p.add_argument("--rotate-every", type=int, default=None, metavar="N",
                   help="generate a fresh random server seed every N words (N=1 changes the server seed "
                        "constantly); the nonce walks 0..N-1 within each seed, as in commit-reveal")
    p.add_argument("--bits", type=int, choices=(32, 52), default=32,
                   help="source draw width: 32 (Stake-style, default) or 52 (bustabit-style, bit-packed "
                        "into 32-bit words); dieharder always reads 32-bit words")
    p.add_argument("-o", "--output", default="-",
                   help="output path, or '-' for stdout (default)")
    p.add_argument("--format", choices=("raw", "ascii"), default="raw",
                   help="raw binary uint32 words (default) or ascii decimal lines for dieharder -g 202")
    p.add_argument("--little-endian", action="store_true",
                   help="write raw words little-endian (default: big-endian)")
    return p


def _silence_broken_pipe() -> None:
    """When dieharder (or ``head``) closes the pipe early, suppress the spurious
    BrokenPipeError Python raises while flushing stdout at exit, by pointing the
    stdout fd at /dev/null (per the Python docs)."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except OSError:
        pass


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Build an infinite source of `bits`-wide draws, fixed-seed or rotating.
    if args.rotate_every is not None:
        if args.rotate_every < 1:
            parser.error("--rotate-every must be >= 1")
        make = rotating_uint32_stream if args.bits == 32 else rotating_uint52_stream
        source = make(args.client_seed, rotate_every=args.rotate_every)
    else:
        if args.server_seed is None:
            parser.error("--server-seed is required unless --rotate-every is set")
        make = uint32_stream if args.bits == 32 else uint52_stream
        source = make(args.server_seed, args.client_seed, args.start_nonce)

    # 32-bit words for dieharder: pass through, or bit-pack the wider draw.
    words = source if args.bits == 32 else repack_to_uint32(source, args.bits)
    if args.count is not None:
        words = islice(words, args.count)

    ascii_mode = args.format == "ascii"
    if args.output == "-":
        out, close = (sys.stdout if ascii_mode else sys.stdout.buffer), False
    else:
        out, close = open(args.output, "w" if ascii_mode else "wb"), True

    try:
        if ascii_mode:
            for r_int in words:
                out.write(f"{r_int}\n")
        else:
            write_words(out, words, big_endian=not args.little_endian)
    except BrokenPipeError:
        # dieharder closes the pipe once it has read enough -- that's normal.
        _silence_broken_pipe()
    finally:
        if close:
            out.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
