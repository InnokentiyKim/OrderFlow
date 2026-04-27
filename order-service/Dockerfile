FROM python:3.14-slim AS builder

WORKDIR /web-app/

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv venv /web-app/.venv && \
    VIRTUAL_ENV=/web-app/.venv uv sync --frozen --no-dev --no-install-project


FROM python:3.14-slim

WORKDIR /web-app/

COPY --from=builder /web-app/.venv ./.venv

COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY entrypoint.sh ./

ENV VIRTUAL_ENV=/web-app/.venv \
    PATH="/web-app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /web-app && \
    chmod +x entrypoint.sh

USER appuser

EXPOSE 8002

CMD ["./entrypoint.sh"]
