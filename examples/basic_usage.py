"""Minimal usage example for spingo-games-rng.

Run with:  python examples/basic_usage.py
"""
from spingo_games_rng import (
    uniform32_from_hash,
    uniform32_float_from_hash,
    generate_server_seed,
    generate_client_seed,
    hash_seed,
)


def main() -> None:
    # Commit-reveal: generate a fresh server/client seed pair. The server seed
    # is secret; its hash is the commitment shown to the player up front.
    fresh_server = generate_server_seed()
    fresh_client = generate_client_seed()
    print("Freshly generated seeds (commit-reveal scheme):")
    print(f"  server_seed      = {fresh_server}")
    print(f"  client_seed      = {fresh_client}")
    print(f"  commit hash      = {hash_seed(fresh_server)}\n")

    # Fixed seeds below so the printed draws are reproducible.
    server_seed = "server"
    client_seed = "client"

    print("Single draws (verifiable: same seeds+nonce -> same result):")
    for nonce in range(5):
        r_int, hex_digest = uniform32_from_hash(server_seed, client_seed, nonce)
        r_float, _, _ = uniform32_float_from_hash(server_seed, client_seed, nonce)
        print(f"  nonce={nonce:>2}  uint32={r_int:>10}  "
              f"float={r_float:.6f}  digest={hex_digest[:8]}...")

    print("\nFirst 10 uint32 draws (nonce 0..9):")
    words = [uniform32_from_hash(server_seed, client_seed, n)[0] for n in range(10)]
    print("  " + ", ".join(str(w) for w in words))


if __name__ == "__main__":
    main()
