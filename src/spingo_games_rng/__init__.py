"""spingo-games-rng: HMAC-SHA256 32-bit and 52-bit uniform RNG primitives for
provably-fair games.
"""
from .core import (
    uniform32_from_hash,
    uniform52_from_hash,
    uniform32_float_from_hash,
    uniform52_float_from_hash,
    uniform32_decimal_from_hash,
    uniform52_decimal_from_hash,
)
from .seeds import generate_server_seed, generate_client_seed, hash_seed

__version__ = "0.1.0"

__all__ = [
    "uniform32_from_hash",
    "uniform52_from_hash",
    "uniform32_float_from_hash",
    "uniform52_float_from_hash",
    "uniform32_decimal_from_hash",
    "uniform52_decimal_from_hash",
    "generate_server_seed",
    "generate_client_seed",
    "hash_seed",
]
