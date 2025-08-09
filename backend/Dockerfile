# Minimal Dockerfile (optional) for platforms that prefer containers
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY app /app/app

ENV UV_LINK_MODE=copy
RUN uv sync --frozen

ENV PORT=8000
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


