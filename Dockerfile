FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    CACHE_DIR=/tmp/cache \
    PORT=8080

WORKDIR /app

# Semgrep is installed separately from the app's dependencies (avoids version conflicts)
RUN pip install --no-cache-dir semgrep==1.181.0

# uv installs the app dependencies exactly as locked in uv.lock
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH"

COPY app ./app
COPY rules ./rules

# Hardening: run as an unprivileged user (files are owned by root, so the app can't modify its own code)
RUN useradd --uid 10001 --no-create-home appuser
USER appuser

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.api:app --host 0.0.0.0 --port ${PORT}"]
