FROM python:3.12-slim

# System deps for weasyprint (PDF export) + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies (cached layer — only rebuilds when lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Defaults — override via env_file / environment in compose
ENV GARMINVIEW_DB_BACKEND=mariadb
ENV GARMINVIEW_HEALTH_DATA_DIR=/data/HealthData
ENV GARMINVIEW_LOG_DIR=/app/logs

EXPOSE 8000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
