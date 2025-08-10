# Dockerfile - Fixed uv path
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH (it installs to /root/.local/bin)
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml .
COPY app/ ./app/

# Install dependencies with uv
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -e .

# Run with uv's venv
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]