FROM node:22-slim AS css
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY input.css tokens.css base.css gantt.css ./
COPY templates ./templates
COPY static ./static
RUN npm run css:build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_COMPILE_BYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
COPY --from=css /app/static/css/output.css static/css/output.css
ENV PATH="/app/.venv/bin:$PATH" DJANGO_SETTINGS_MODULE=config.settings.production
RUN useradd --create-home scope && mkdir -p /app/media /app/staticfiles && chown -R scope /app/media /app/staticfiles
USER scope
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
