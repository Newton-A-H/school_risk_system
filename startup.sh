#!/bin/sh
set -e

PORT_VALUE="${PORT:-8000}"
WORKERS="${GUNICORN_WORKERS:-2}"
TIMEOUT="${GUNICORN_TIMEOUT:-600}"

exec gunicorn \
  --bind "0.0.0.0:${PORT_VALUE}" \
  --workers "${WORKERS}" \
  --timeout "${TIMEOUT}" \
  --access-logfile - \
  --error-logfile - \
  wsgi:app
