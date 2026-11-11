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

# Security: run as non-root user
RUN groupadd -g 1000 aias && \
    useradd -u 1000 -g aias -d /app -s /bin/bash aias

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

# Production entry: verify database connection and start Gunicorn WSGI server
CMD ["sh", "-c", "python -c 'from database.db import db_manager; print(\"[AIAS] Database check:\", db_manager.health_check())' && exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers ${WEB_CONCURRENCY:-4} --threads ${GUNICORN_THREADS:-2} --timeout ${GUNICORN_TIMEOUT:-120} --access-logfile - --error-logfile - 'app:create_app()'"]
