# spingo-games-rng: one multi-stage Dockerfile, two build targets.
#
#   --target lib        library + unit tests (pure Python, light, default)
#   --target dieharder  the above + dieharder for the statistical battery (heavy)
#
# docker-compose picks the target per service; or build directly:
#   docker build --target lib       -t spingo-games-rng:lib .
#   docker build --target dieharder -t spingo-games-rng:dieharder .

# --- base: install the package once; both targets branch off this. ----------
FROM python:3.11-slim AS base
WORKDIR /app
# Copy metadata first so the pip layer is cached unless the project changes.
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
RUN pip install --no-cache-dir -e ".[test]"

# --- lib: library + unit tests. Pure Python, no dieharder. ------------------
FROM base AS lib
COPY examples ./examples
# Default: run the unit-test suite (override to run the example).
CMD ["python", "-m", "pytest", "-q"]

# --- dieharder: adds dieharder (Debian) for the statistical battery. --------
FROM base AS dieharder
RUN apt-get update \
    && apt-get install -y --no-install-recommends dieharder \
    && rm -rf /var/lib/apt/lists/*
COPY run_dieharder.sh ./
RUN chmod +x run_dieharder.sh
# Default: run the dieharder battery against the stream (tests/dieharder_feed.py).
ENTRYPOINT []
CMD ["./run_dieharder.sh"]
