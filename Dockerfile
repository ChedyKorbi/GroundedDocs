FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Layer 1: dependencies only (heavily cached across rebuilds).
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-group dev --no-install-project

# Layer 2: application code.
COPY . .

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
