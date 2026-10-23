# Multi-stage production container build for ChronoLab
FROM python:3.11-slim as base

# Set environment variables for performance and output flushing
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=5000

# Install system dependencies (build-essential, libpq for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create non-root system user for medical data security compliance
RUN adduser --disabled-password --gecos "" chronouser \
    && chown -R chronouser:chronouser /app
USER chronouser

# Expose server port
EXPOSE 5000

# Health check using native Python standard library
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/healthz')" || exit 1

# Launch production Gunicorn worker cluster
CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120"]
