#!/usr/bin/env bash
set -euo pipefail

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"

case "${1:-web}" in
  migrate)
    echo "[entrypoint] running migrations"
    exec python manage.py migrate --noinput
    ;;
  web)
    echo "[entrypoint] starting gunicorn on :${PORT:-8000}"
    exec gunicorn config.wsgi:application \
      --bind "0.0.0.0:${PORT:-8000}" \
      --workers "${WEB_CONCURRENCY:-2}" \
      --threads 2 \
      --worker-class gthread \
      --timeout 60 \
      --access-logfile - \
      --error-logfile - \
      --capture-output \
      --enable-stdio-inheritance
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