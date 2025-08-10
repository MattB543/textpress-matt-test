# Minimal Dockerfile (optional) for platforms that prefer containers
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock
COPY app /app/app

# System libs commonly required by markdown/html tooling (weasyprint/opencv/fonts etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
      libffi8 libxml2 libxslt1.1 libjpeg62-turbo libgl1 \
      fonts-dejavu-core ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy
# Install dependencies exactly as pinned in uv.lock
RUN uv sync --frozen

ENV PORT=8000
EXPOSE 8000
# Use shell form so $PORT from the platform is honored (fallback to 8000 locally)
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]


