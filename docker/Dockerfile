# ── Stage 1: Build Tailwind CSS ───────────────────────────────────────────────
FROM node:20-alpine AS css-builder

WORKDIR /build
RUN npm init -y \
 && npm install -D tailwindcss@3 @tailwindcss/forms autoprefixer postcss \
                   htmx.org@2 alpinejs@3

COPY tailwind.config.js postcss.config.js ./
COPY app/templates ./app/templates/
COPY app/static/css/input.css ./app/static/css/input.css

RUN npx tailwindcss -i app/static/css/input.css -o app/static/css/output.css --minify

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      sqlite3 \
      curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN useradd --create-home --shell /bin/bash app

WORKDIR /home/app/ha-analyzer
ENV PYTHONPATH=/home/app/ha-analyzer

COPY pyproject.toml ./
COPY app/__init__.py ./app/__init__.py
RUN uv pip install --system --no-cache .

COPY app ./app
COPY migrations ./migrations

COPY --from=css-builder /build/app/static/css/output.css ./app/static/css/output.css
COPY --from=css-builder /build/node_modules/htmx.org/dist/htmx.min.js ./app/static/js/htmx.min.js
COPY --from=css-builder /build/node_modules/alpinejs/dist/cdn.min.js ./app/static/js/alpine.min.js

RUN mkdir -p /data/db \
 && chown -R app:app . /data
USER app

EXPOSE 8104

# Single worker is mandatory — APScheduler must not be duplicated across workers.
CMD ["gunicorn", \
     "--workers", "1", \
     "--worker-class", "gthread", \
     "--threads", "8", \
     "--bind", "0.0.0.0:8104", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "app:create_app()"]
