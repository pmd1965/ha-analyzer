#!/bin/bash
set -e

flask db upgrade

exec gunicorn \
    --workers 1 \
    --worker-class gthread \
    --threads 8 \
    --bind 0.0.0.0:8104 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "app:create_app()"
