"""Provably-fair crash multiplier.

Maps a single HMAC-SHA256 draw (:func:`uniform32_from_hash`) into the final
crash multiplier.
"""
from decimal import Decimal

from .core import uniform32_from_hash


def calculate_crash_multiplier(
    rtp: Decimal, max_multiplier: Decimal,
    server_seed: str, client_seed: str, nonce: int,
) -> tuple[Decimal, str, int]:
    """Crash multiplier -- provably-fair.

    ``rtp`` is ``(1 - houseEdge)`` (0.97 = 3% house edge); the result is rounded
    to 2 decimal places and capped to [1, max_multiplier].

    Returns (multiplier, hex_digest, r_int) -- the last two are for audit.
    """
    e32 = Decimal(2 ** 32)
    r_int, hex_digest = uniform32_from_hash(server_seed, client_seed, nonce)
    if not (0 <= r_int < e32):
        raise ValueError("r must be 32-bit: 0 <= r < 2^32")
    raw = rtp * (e32 / (r_int + 1))
    multiplier = max(min(round(raw, 2), max_multiplier), Decimal(1))
    return multiplier, hex_digest, r_int
