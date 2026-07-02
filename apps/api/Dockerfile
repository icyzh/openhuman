# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependency definition files
COPY pyproject.toml uv.lock ./

# Install dependencies only (cached if files do not change)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Stage 2: Final runtime image
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source code
COPY app /app/app
COPY alembic.ini /app/
COPY alembic /app/alembic

# Create storage directory for uploads
RUN mkdir -p /app/uploads

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

