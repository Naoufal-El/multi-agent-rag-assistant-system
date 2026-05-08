FROM python:3.12-slim

WORKDIR /apps

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files first (for Docker layer caching)
COPY requirements.txt /apps/requirements.txt

# Install dependencies with uv (much faster and more reliable than pip)
RUN uv pip install --system --no-cache -r /apps/requirements.txt

# Copy application source
COPY apps /apps

EXPOSE 8000

CMD ["uvicorn", "apps.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--workers", "1"]