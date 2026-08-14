# syntax=docker/dockerfile:1
#
# Multi-stage build: the builder resolves the full dependency tree (incl. the
# `ml` extra for embeddings/rerankers) into a venv; the runtime stage copies
# only that venv + application code for a lean final image.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Layer 1: dependencies only (heavily cached across rebuilds).
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-group dev --extra ml --no-install-project

# Layer 2: application code (kept in a separate layer for cache efficiency).
COPY . .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HF_HOME="/cache/huggingface" \
    GROUNDEDDOCS_SEED_ON_BOOT=true

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/pyproject.toml /app/uv.lock /app/

# Application code (build context excludes .venv/.git/caches via .dockerignore).
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
