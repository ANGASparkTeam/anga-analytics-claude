# ---- build: resolve deps from uv.lock into /app/.venv ----
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app

# Dependencies first (cached layer while only source changes)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the project itself (non-editable so the venv is self-contained)
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---- runtime: slim image, non-root ----
FROM python:3.12-slim-bookworm AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /home/app --create-home app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
# Example property map; production mounts the real one from Secret Manager
# at /config/properties.yaml (see deploy/deploy.sh).
COPY --chown=app:app properties.example.yaml /app/properties.example.yaml

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FASTMCP_HOME=/tmp/fastmcp \
    PORT=8080
WORKDIR /app
USER app
EXPOSE 8080

CMD ["ga4-mcp"]
