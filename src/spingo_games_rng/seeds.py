"""Seed generation and hashing for the commit-reveal scheme.

Server seed: secret, revealed to the player only after the round resolves.
Client seed: public, contributes to the outcome via HMAC.
"""
import hashlib
import secrets
import string

__all__ = ["generate_server_seed", "generate_client_seed", "hash_seed"]


def generate_server_seed(byte_length: int = 20) -> str:
    """Random hex seed. Default 20 bytes = 40 hex chars."""
    return secrets.token_hex(byte_length)


def generate_client_seed(length: int = 20) -> str:
    """Random alphanumeric (A-Z a-z 0-9) of the given ``length``."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def hash_seed(seed: str) -> str:
    """SHA-256 hex digest. Used as the commit-hash for a server_seed."""
    return hashlib.sha256(seed.encode('utf-8')).hexdigest()
