"""HMAC-SHA256 primitives for extracting deterministic uniform values
(32-bit Stake-style and 52-bit bustabit-style) from
(server_seed, client_seed, nonce).

The same seed + nonce always yields the same result, which is what makes the
output verifiable after the fact (provably-fair gambling style).
"""
import hashlib
import hmac
from decimal import Decimal

__all__ = [
    "uniform32_from_hash",
    "uniform52_from_hash",
    "uniform32_float_from_hash",
    "uniform52_float_from_hash",
    "uniform32_decimal_from_hash",
    "uniform52_decimal_from_hash",
]

# Divisor mapping a uint32 into the half-open interval [0, 1).
_E32 = float(2 ** 32)
# Divisor mapping a uint52 into the half-open interval [0, 1).
_E52 = float(2 ** 52)
# Decimal divisors for the exact-precision uint -> [0, 1) mappings.
_E32_DECIMAL = Decimal(2 ** 32)
_E52_DECIMAL = Decimal(2 ** 52)


def uniform32_from_hash(server_seed: str, client_seed: str, nonce: int) -> tuple[int, str]:
    """32-bit uniform integer.

    HMAC message: ``{client_seed}:{nonce}:0`` -- the trailing ``:0`` is the
    format expected by provably-fair verifiers. The key is the server seed.
    The first 8 hex chars of the SHA-256 HMAC digest are taken as a big-endian
    uint32.

    Returns ``(r_int in [0, 2**32), full_hex_digest)``.
    """
    msg = f"{client_seed}:{nonce}:0".encode("utf-8")
    key = server_seed.encode("utf-8")
    hex_digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    r_int = int(hex_digest[:8], 16)  # 32 bits
    return r_int, hex_digest


def uniform52_from_hash(server_seed: str, client_seed: str, nonce: int) -> tuple[int, str]:
    """52-bit uniform integer.

    First 13 hex chars of the digest as a big-endian uint52 (52 = double
    mantissa width). HMAC message ``{client_seed}:{nonce}`` -- no trailing
    ``:0`` (the ``:0`` belongs to the 32-bit :func:`uniform32_from_hash`).

    Returns ``(r_int in [0, 2**52), full_hex_digest)``.
    """
    msg = f"{client_seed}:{nonce}".encode("utf-8")
    key = server_seed.encode("utf-8")
    hex_digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    r_int = int(hex_digest[:13], 16)  # 52 bits
    return r_int, hex_digest


def uniform32_float_from_hash(server_seed: str, client_seed: str, nonce: int) -> tuple[float, str, int]:
    """The 32-bit value mapped into [0, 1).

    Returns ``(r in [0, 1), full_hex_digest, r_int)`` -- ``r_int`` is the source
    uint32, returned too so callers needn't recover it from ``r``.
    """
    r_int, hex_digest = uniform32_from_hash(server_seed, client_seed, nonce)
    return r_int / _E32, hex_digest, r_int


def uniform52_float_from_hash(server_seed: str, client_seed: str, nonce: int) -> tuple[float, str, int]:
    """The 52-bit value mapped into [0, 1).

    Returns ``(r in [0, 1), full_hex_digest, r_int)`` -- ``r_int`` is the source
    uint52, returned too so callers needn't recover it from ``r``.
    """
    r_int, hex_digest = uniform52_from_hash(server_seed, client_seed, nonce)
    return r_int / _E52, hex_digest, r_int


def uniform32_decimal_from_hash(server_seed: str, client_seed: str, nonce: int) -> tuple[Decimal, str, int]:
    """Exact ``Decimal`` r in [0, 1) from the 32-bit value.

    Uses ``Decimal`` arithmetic so the mapping is exact (no binary
    floating-point rounding), which is what game CDF formulas rely on.

    Returns ``(r in [0, 1), full_hex_digest, r_int)`` -- ``r_int`` is the source
    uint32, returned too so callers needn't recover it from ``r``.
    """
    r_int, hex_digest = uniform32_from_hash(server_seed, client_seed, nonce)
    return Decimal(r_int) / _E32_DECIMAL, hex_digest, r_int


def uniform52_decimal_from_hash(server_seed: str, client_seed: str, nonce: int) -> tuple[Decimal, str, int]:
    """Exact ``Decimal`` r in [0, 1) from the 52-bit value.

    Uses ``Decimal`` arithmetic so the mapping is exact (no binary
    floating-point rounding), which is what game CDF formulas rely on.

    Returns ``(r in [0, 1), full_hex_digest, r_int)`` -- ``r_int`` is the source
    uint52, returned too so callers needn't recover it from ``r``.
    """
    r_int, hex_digest = uniform52_from_hash(server_seed, client_seed, nonce)
    return Decimal(r_int) / _E52_DECIMAL, hex_digest, r_int
