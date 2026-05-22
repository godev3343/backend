# ---------- builder ----------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---------- runtime ----------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 gdal-bin libgdal36 binutils libproj25 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app . .

RUN mkdir -p /app/staticfiles /app/.gunicorn && \
    chown -R app:app /app/staticfiles /app/.gunicorn

RUN chmod +x deploy/entrypoint.sh

RUN SECRET_KEY="build-only-dummy-secret-key-32chars-min-aaaa" \
    DATABASE_URL="postgres://u:p@localhost:5432/d" \
    REDIS_URL="redis://localhost:6379/0" \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    DEBUG=false \
    python manage.py collectstatic --noinput

USER app
EXPOSE 8000

ENTRYPOINT ["./deploy/entrypoint.sh"]
CMD ["web"]