#!/usr/bin/env bash
# Run the dieharder battery against the RNG stream (tests/dieharder_feed.py).
#
# Usage:
#   ./run_dieharder.sh                       # full battery, default seeds
#   ./run_dieharder.sh -d 0                  # single test (diehard birthdays)
#   SERVER=foo CLIENT=bar ./run_dieharder.sh # custom seeds
#   ROTATE=1 ./run_dieharder.sh              # fresh random server seed per word
#   ROTATE=1000 ./run_dieharder.sh           # rotate server seed every 1000 words
#   BITS=52 ./run_dieharder.sh               # 52-bit (bustabit) draw, bit-packed
#
# Any extra args are passed straight through to dieharder. Defaults to "-a"
# (run all tests) when no test selection is given.
set -euo pipefail

# The dieharder feed lives under tests/ (it is validation tooling, not part of
# the installed package). Resolve it relative to this script so the harness runs
# from any cwd.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FEED="$HERE/tests/dieharder_feed.py"

SERVER="${SERVER:-server}"
CLIENT="${CLIENT:-client}"
ROTATE="${ROTATE:-}"   # if set, rotate the server seed every ROTATE words
BITS="${BITS:-32}"     # source draw width: 32 (default) or 52 (bit-packed)

if ! command -v dieharder >/dev/null 2>&1; then
  echo "dieharder not found. Install it first, e.g.:" >&2
  echo "  macOS:  brew install dieharder" >&2
  echo "  Debian: sudo apt-get install dieharder" >&2
  exit 1
fi

# Default to the full battery if the caller didn't pick tests.
DIEHARDER_ARGS=("$@")
if [ ${#DIEHARDER_ARGS[@]} -eq 0 ]; then
  DIEHARDER_ARGS=(-a)
fi

# Build the generator command: fixed server seed, or rotating server seed.
if [ -n "$ROTATE" ]; then
  echo "Feeding RNG stream (rotating server seed every $ROTATE word(s), client='$CLIENT', bits=$BITS) into dieharder..." >&2
  GEN=(python "$FEED" --client-seed "$CLIENT" --rotate-every "$ROTATE" --bits "$BITS")
else
  echo "Feeding RNG stream (server='$SERVER' client='$CLIENT' bits=$BITS) into dieharder..." >&2
  GEN=(python "$FEED" --server-seed "$SERVER" --client-seed "$CLIENT" --bits "$BITS")
fi

# -g 200 = read raw 32-bit words from stdin.
"${GEN[@]}" | dieharder -g 200 "${DIEHARDER_ARGS[@]}"
