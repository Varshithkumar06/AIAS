# ── Build Stage ──
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Production Stage ──
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=5000

# Install Redis server and procps for embedded cache & rate limiting
RUN apt-get update && \
    apt-get install -y --no-install-recommends redis-server procps && \
    rm -rf /var/lib/apt/lists/*

# Security: run as non-root user
RUN groupadd -g 1000 aias && \
    useradd -u 1000 -g aias -d /app -s /bin/bash aias && \
    mkdir -p /app /var/lib/redis /var/log/redis && \
    chown -R aias:aias /var/lib/redis /var/log/redis

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application files (excluding items in .dockerignore)
COPY . .

# Set proper permissions for the aias user
RUN chown -R aias:aias /app

USER aias

EXPOSE 5000

# Container healthcheck via /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\", \"5000\")}/health', timeout=4)" || exit 1

# Production entry: start Redis in background if targeting localhost, verify database connection, and start Gunicorn WSGI server
CMD ["sh", "-c", "([ -z \"$REDIS_URL\" ] || echo \"$REDIS_URL\" | grep -qE 'localhost|127\\.0\\.0\\.1') && redis-server --daemonize yes --dir /tmp --protected-mode no 2>/dev/null || true; python -c 'from database.db import db_manager; print(\"[AIAS] Database check:\", db_manager.health_check())' && exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${WEB_CONCURRENCY:-4} --threads ${GUNICORN_THREADS:-2} --timeout ${GUNICORN_TIMEOUT:-120} --access-logfile - --error-logfile - 'app:create_app()'"]
