# spingo-games-rng

HMAC-SHA256 uniform RNG primitives (**`uniform32_from_hash`** /
**`uniform52_from_hash`**) for provably-fair games, plus the reference Crash
outcome mapping (**`calculate_crash_multiplier`**) and a ready-to-run
[dieharder](https://webhome.phy.duke.edu/~rgb/General/dieharder.php) harness.

## What it does

Given a server seed, a client seed, and a nonce, the package derives a
deterministic uniform integer. The same inputs always produce the same output,
so any result can be verified after the fact. Two widths:

```
# 32-bit (Stake-style — crash/aviator verifiers)
HMAC_SHA256(key=server_seed, msg="{client_seed}:{nonce}:0")  → int(digest[:8],  16)

# 52-bit (bustabit-style — IEEE-754 double mantissa, 13 hex chars)
HMAC_SHA256(key=server_seed, msg="{client_seed}:{nonce}")    → int(digest[:13], 16)
```

Each width comes in three forms — e.g. for 52-bit: the raw integer
(`uniform52_from_hash`), plus `float` (`uniform52_float_from_hash`) and exact
`Decimal` (`uniform52_decimal_from_hash`) mapped into `[0, 1)`. Same pattern
for 32-bit.

## Use as a library

```python
from spingo_games_rng import uniform32_from_hash, uniform52_decimal_from_hash

r_int, digest = uniform32_from_hash("server", "client", 1)   # (2296099867, "88dbb41b...")
r_dec, digest, r_int = uniform52_decimal_from_hash("server", "client", 1)  # Decimal in [0,1) + source int
```

Seeds for the commit-reveal scheme:

```python
from spingo_games_rng import generate_server_seed, generate_client_seed, hash_seed

server_seed = generate_server_seed()   # secret: 40 hex chars
client_seed = generate_client_seed()   # public: 20 alphanumeric chars
commit = hash_seed(server_seed)        # SHA-256 commitment, published up front
```

## Crash outcome mapping

`calculate_crash_multiplier` is the reference mapping for the Crash game — it
turns a single HMAC draw into the final crash multiplier:

```python
from decimal import Decimal
from spingo_games_rng import calculate_crash_multiplier

rtp = Decimal("0.97")
max_multiplier = Decimal("1000")
multiplier, digest, r_int = calculate_crash_multiplier(
    rtp, max_multiplier, server_seed, client_seed, nonce,
)
```

The result is deterministic, rounded to 2 decimals, and bounded to
`[1, max_multiplier]`; the house edge is applied through `rtp`. The draw feeds a
division (not an integer-range/modulo mapping), so the outcome is unbiased and
needs no rejection sampling.

In a live round the server seed is committed (its hash published) before bets,
the client seed combines the participating players' seeds, the nonce is the
round number, and the server seed is revealed afterwards for verification. See
`tests/test_crash.py` for a full round (commit → derive → reveal → verify), a
frozen audit vector, and a Monte-Carlo simulation showing the empirical RTP
converges to the configured RTP.

## Install & test

```bash
pip install -e ".[test]"
pytest
python examples/basic_usage.py
```

## Docker

One multi-stage Dockerfile, two build targets — compose picks the right one per
service:

- **`lib`** — pure Python: the package + unit tests. Used by `test`, `example`.
- **`dieharder`** — adds dieharder (Debian) for the statistical battery. Used by
  `smoke`, `dieharder`. Heavier; only built when you run those.

```bash
docker compose run --rm test       # pytest suite            (lib)
docker compose run --rm example    # usage example           (lib)
docker compose run --rm smoke      # one quick dieharder test (dieharder)
docker compose run --rm dieharder  # full battery — hours, run detached (dieharder)
```

Override the default seeds via env: `SERVER=<seed> CLIENT=<seed> docker compose run --rm dieharder`.

The full battery is long, so run it detached so it survives an SSH disconnect:

```bash
docker compose run --rm -d --name dieharder dieharder
docker logs -tf dieharder          # follow progress with timestamps
```

### Rotating the server seed

By default one server seed is fixed and the nonce walks `0, 1, 2, …`. To rotate
the server seed (as in commit-reveal, where each seed serves a run of nonces
then rotates), set `ROTATE=N` — a fresh random server seed every `N` words, with
the nonce walking `0..N-1` within each:

```bash
ROTATE=100 docker compose run --rm smoke      # rotate every 100 words
```

### Testing the 52-bit draw

dieharder reads 32-bit words, so the 52-bit (bustabit) draw is bit-packed into a
continuous 32-bit word stream (every bit used once). Select it with `BITS=52`:

```bash
BITS=52 docker compose run --rm smoke         # 52-bit source, bit-packed
```

## Without Docker

The dieharder harness is validation tooling under `tests/`, not part of the
shipped library — `tests/dieharder_feed.py` emits a stream of 32-bit words (one
HMAC draw per nonce, the RNG under test with no extra mixing). Install dieharder
(`brew install dieharder` / `apt-get install dieharder`), then either use the
helper script:

```bash
./run_dieharder.sh                       # full battery, default seeds
./run_dieharder.sh -d 0                  # one test
SERVER=<seed> CLIENT=<seed> ./run_dieharder.sh # override default seeds
ROTATE=100 ./run_dieharder.sh            # rotate every 100 words
BITS=52 ./run_dieharder.sh               # 52-bit draw, bit-packed
```

or drive dieharder directly with the feed script:

```bash
python tests/dieharder_feed.py -s server -c client | dieharder -g 200 -a            # 32-bit
python tests/dieharder_feed.py -s server -c client --bits 52 | dieharder -g 200 -a  # 52-bit
python tests/dieharder_feed.py -c client --rotate-every 100 --bits 52 | dieharder -g 200 -a
```

The stream helpers live in `tests/_streams.py` (`uint32_stream`, `uint52_stream`,
`rotating_uint32_stream`, `rotating_uint52_stream`, `repack_to_uint32`) if you
want to drive them from Python.

A recorded full-battery run (rotating seed, 32-bit) is kept as evidence in
[tests/results/dieharder.log](tests/results/dieharder.log); its first line shows
the run parameters.

> dieharder finds *statistical* weaknesses; HMAC-SHA256 is cryptographically
> strong, so it is expected to pass. An occasional `WEAK` in a full run is
> normal statistical noise, not a failure.
