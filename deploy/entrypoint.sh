#!/usr/bin/env bash
set -euo pipefail

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"

case "${1:-web}" in
  migrate)
    echo "[entrypoint] running migrations"
    exec python manage.py migrate --noinput
    ;;
  web)
    echo "[entrypoint] starting daphne (ASGI: HTTP + WebSocket) on :${PORT:-8000}"
    # Сервим через daphne (ASGI), а не gunicorn (WSGI), потому что чату нужен
    # WebSocket (/ws/chat) на том же домене. daphne обслуживает и обычный HTTP
    # (Django-вьюхи + WhiteNoise-статика), и WS (Channels) одним процессом.
    # --proxy-headers: Railway терминирует TLS и проксирует — доверяем
    #   X-Forwarded-* (схема/IP); SECURE_PROXY_SSL_HEADER в prod.py это учитывает.
    # Один async-процесс тянет realtime-чат MVP; для горизонтального масштаба
    # поднимаем несколько инстансов — group_send идёт через Redis channel layer.
    exec daphne \
      -b 0.0.0.0 \
      -p "${PORT:-8000}" \
      --proxy-headers \
      --access-log - \
      config.asgi:application
    ;;
  worker)
    exec celery -A config worker -l info -Q default,media,ai \
      --concurrency="${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    exec celery -A config beat -l info \
      --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ;;
  *)
    exec "$@"
    ;;
esac