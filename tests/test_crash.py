"""Usage scenario for the Crash game-outcome mapping.

Shows how ``calculate_crash_multiplier`` is used to run a full provably-fair
round end to end -- commit, derive, reveal, and independent verification -- and
locks the algorithm with a frozen audit vector.
"""
from decimal import Decimal

from spingo_games_rng import (
    calculate_crash_multiplier,
    generate_server_seed,
    generate_client_seed,
    hash_seed,
)

RTP = Decimal("0.97")
MAX_MULTIPLIER = Decimal("1000")


def test_provably_fair():
    """One round, exactly as the game runs it."""
    # 1. Round creation: the server draws a secret seed and publishes only its
    #    hash (the commitment) -- the player sees this before placing a bet.
    server_seed = generate_server_seed()
    commitment = hash_seed(server_seed)

    # 2. The round's client seed combines the first three players to bet: each
    #    has a persistent client seed, concatenated together (the nonce is the
    #    sequential round number). Players influence the outcome but cannot
    #    predict it, since the server seed is already committed.
    client_seed1 = generate_client_seed()
    client_seed2 = generate_client_seed()
    client_seed3 = generate_client_seed()
    client_seed = "".join([client_seed1, client_seed2, client_seed3])
    nonce = 42

    # 3. When bets close, the multiplier is derived deterministically from
    #    (server_seed, client_seed, nonce).
    multiplier, hex_digest, r_int = calculate_crash_multiplier(
        RTP, MAX_MULTIPLIER, server_seed, client_seed, nonce,
    )

    # The outcome is a valid 2-decimal multiplier within the configured bounds.
    assert Decimal(1) <= multiplier <= MAX_MULTIPLIER
    assert multiplier.as_tuple().exponent >= -2      # at most 2 decimal places
    assert 0 <= r_int < 2 ** 32
    assert len(hex_digest) == 64

    # 4. Reveal: after the round the server_seed is published. Anyone can verify
    #    the commitment and re-run the exact computation to confirm the result.
    assert hash_seed(server_seed) == commitment
    replay = calculate_crash_multiplier(RTP, MAX_MULTIPLIER, server_seed, client_seed, nonce)
    assert replay == (multiplier, hex_digest, r_int)  # fully deterministic


def test_audit_vector():
    """Frozen known-answer vector -- locks the formula against drift and lets a
    third party reproduce and verify the result independently."""
    m, hex_digest, r_int = calculate_crash_multiplier(
        RTP, MAX_MULTIPLIER, "server", "client", 1,
    )
    assert hex_digest == "88dbb41b566bc5aefb6e787840e6a4405c6a769fd9a332c9b61e938c4a86132e"
    assert r_int == 2296099867
    assert m == Decimal("1.81")


def test_multiplier_capped():
    """The multiplier stays within [1, MAX_MULTIPLIER], and over a large sample
    both clamps are exercised: the lower bound holds it at 1.00 and the upper
    bound caps it at MAX_MULTIPLIER (fixed seeds make the sample hit both)."""
    multipliers = [calculate_crash_multiplier(RTP, MAX_MULTIPLIER, "server", "client", n)[0]
                   for n in range(100_000)]
    assert all(Decimal(1) <= m <= MAX_MULTIPLIER for m in multipliers)
    assert min(multipliers) == Decimal(1)            # lower clamp fires
    assert max(multipliers) == MAX_MULTIPLIER        # upper clamp fires


def _simulate_rtp(cashout, rounds):
    """Empirical return-to-player for a fixed auto-cashout (bet = 1), with the
    nonce walking 1..rounds. Each round pays ``cashout`` if the crash multiplier
    reached it, else loses the 1-unit bet.

    Seeds are freshly generated here (server seed + three players' client seeds,
    concatenated), so each call is an independent provably-fair simulation.
    """
    server_seed = generate_server_seed()
    client_seed1 = generate_client_seed()
    client_seed2 = generate_client_seed()
    client_seed3 = generate_client_seed()
    client_seed = "".join([client_seed1, client_seed2, client_seed3])

    total = Decimal(0)
    for nonce in range(1, rounds + 1):
        m, _, _ = calculate_crash_multiplier(RTP, MAX_MULTIPLIER, server_seed, client_seed, nonce)
        total += (cashout - 1) if m >= cashout else Decimal(-1)
    return 1 + total / rounds


def test_rtp():
    """Empirical RTP converges to the configured RTP across cashout levels --
    the key evidence that the outcome mapping is unbiased. A Monte-Carlo
    simulation; the tolerance covers the random-seed sampling variance.
    """
    rounds = 100_000
    for cashout in (Decimal("1.5"), Decimal("2"), Decimal("5")):
        rtp_fact = _simulate_rtp(cashout, rounds)
        assert abs(rtp_fact - RTP) < Decimal("0.03"), (cashout, rtp_fact)
