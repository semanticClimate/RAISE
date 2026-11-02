# ==============================================================================
# RAISE Academic GraphRAG Studio — Production Multi-Stage Dockerfile
# Stage 1: Rust Acceleration Engine Builder (PyO3 native extension + C-ABI)
# Stage 2: Production Python 3.12-slim Runtime with non-root security & healthcheck
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Native Rust Acceleration Engine Builder (raise_engine)
# ------------------------------------------------------------------------------
FROM rust:1-slim-bookworm AS rust-builder

WORKDIR /build

# Install Python 3.12 dev environment and build dependencies for PyO3
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install maturin for standard PEP 517/621 Python wheel compilation
RUN pip3 install --no-cache-dir --break-system-packages "maturin>=1.5,<2.0"

# Copy Rust crate source
COPY rust/raise_engine /build/rust/raise_engine

WORKDIR /build/rust/raise_engine

# 1. Build release Python wheel via maturin (PyO3 native extension)
RUN maturin build --release --out /build/wheels

# 2. Build C-ABI shared library (.so) with python feature enabled
RUN cargo build --release --features python


# ------------------------------------------------------------------------------
# Stage 2: Production Python 3.12 Runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS base

# System dependencies for PDF parsing, C-extensions, and container healthchecks
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Astral uv for ultra-fast, concurrent dependency resolution & caching
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Build-time argument allowing custom PyTorch wheels (CPU default, cu121/cu124 for CUDA)
ARG TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"

# Install Python requirements with layer caching using uv
COPY requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache "setuptools>=78.1.1" "msgpack>=1.2.1" && \
    uv pip install --system --no-cache --index-strategy unsafe-best-match -r requirements.txt --extra-index-url "${TORCH_INDEX_URL}"

# Copy and install compiled native Rust PyO3 wheel from builder stage
COPY --from=rust-builder /build/wheels /tmp/wheels
RUN uv pip install --system --no-cache /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Copy C-ABI shared library from builder stage
RUN mkdir -p /app/bin
COPY --from=rust-builder /build/rust/raise_engine/target/release/libraise_engine.so /app/bin/libraise_engine.so
COPY --from=rust-builder /build/rust/raise_engine/target/release/libraise_engine.so /usr/local/lib/libraise_engine.so
RUN ldconfig

# Copy codebase
COPY . /app/

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    HF_HUB_VERBOSITY=error \
    HF_HOME=/home/appuser/.cache/huggingface \
    MODELS_DIR=/app/models \
    TOKENIZERS_PARALLELISM=false \
    HOST=0.0.0.0 \
    PORT=8000 \
    RUST_BACKTRACE=1 \
    PYTHONPATH=/app:/app/bin

# Verify Rust acceleration engine loads properly inside container during build
RUN python -c "import raise_engine; print('[DOCKER BUILD] Rust PyO3 acceleration active:', raise_engine.clean_text('Test-\ning  engine'))"

# Create non-root user and set permissions
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/.chromadb_bge_large /app/.runtime /app/data /app/models /home/appuser/.cache/huggingface && \
    chown -R appuser:appuser /app /home/appuser

USER appuser

# Expose HTTP port
EXPOSE 8000

# Container Healthcheck against system health endpoint
HEALTHCHECK --interval=20s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Production Entrypoint
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
