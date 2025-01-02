# Builder Stage
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    libpq-dev \
    gcc \
    python3-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-dev

# Install additional Python packages
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install sentence-transformers && \
    pip install faiss-cpu==1.9.0.post1 && \
    pip install apache-airflow==2.7.3 \
    apache-airflow-providers-celery==3.3.1 \
    apache-airflow-providers-postgres==5.6.0 \
    apache-airflow-providers-redis==3.3.1 \
    apache-airflow-providers-http==4.1.0 \
    apache-airflow-providers-common-sql==1.10.0 \
    croniter==2.0.1 \
    cryptography==42.0.0

# Final Stage 
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libomp-dev \
    curl \
    redis-tools \
    netcat-openbsd \
    wget \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Create user and group
RUN groupadd -g 1001 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

# Create all required directories
RUN mkdir -p \
    /code/ai_services_api/services/search/models \
    /code/logs \
    /code/cache \
    /opt/airflow/logs \
    /opt/airflow/dags \
    /opt/airflow/plugins \
    /opt/airflow/data \
    /code/scripts

# Set permissions
RUN chown -R appuser:appgroup /code && \
    chown -R appuser:appgroup /opt/airflow && \
    chmod -R 775 /code && \
    chmod -R 775 /opt/airflow

# Set working directory
WORKDIR /code

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
COPY --chown=appuser:appgroup . .

# Make scripts executable
RUN chmod +x /code/scripts/init-script.sh

# Set environment variables
ENV TRANSFORMERS_CACHE=/code/cache \
    HF_HOME=/code/cache \
    AIRFLOW_HOME=/opt/airflow \
    PYTHONPATH=/code

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER appuser
