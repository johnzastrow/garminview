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

# Run as an unprivileged user, not root. UID/GID 1000 match the usual first
# account on the host, so the bind-mounted HealthData and .GarminDb folders
# (owned by that account) are writable/readable without changing them.
RUN groupadd --gid 1000 garminview \
    && useradd --uid 1000 --gid 1000 --create-home --home-dir /home/garminview \
       --shell /usr/sbin/nologin garminview

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
ENV HOME=/home/garminview

EXPOSE 8000

COPY entrypoint.sh /entrypoint.sh
# The log directory is the one place under /app the app writes; a new named
# volume mounted here starts with this ownership.
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/logs \
    && chown garminview:garminview /app/logs

USER garminview

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
