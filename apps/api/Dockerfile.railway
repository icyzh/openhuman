# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependency definition files from apps/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./

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

# Copy application source code from apps/api
COPY apps/api/app /app/app
COPY apps/api/alembic.ini /app/
COPY apps/api/alembic /app/alembic

# Create storage directory for uploads
RUN mkdir -p /app/uploads

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
