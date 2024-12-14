# Builder Stage
FROM python:3.11-slim as builder

RUN apt-get update && apt-get install -y \
  build-essential \
  curl \
  wget \
  libpq-dev \
  gcc \
  python3-dev \
  postgresql-client \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && \
  pip install poetry && \
  poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-dev

RUN pip install --index-url https://download.pytorch.org/whl/cpu torch && \
  pip install sentence-transformers && \
  pip install faiss-cpu==1.9.0.post1

# Final Stage 
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
  postgresql-client \
  libomp-dev \
  curl \
  redis-tools \
  netcat-openbsd \
  wget \
  && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1001 appgroup && \
   useradd -u 1000 -g appgroup -s /bin/bash -m appuser

# Create all required directories including Airflow directories
RUN mkdir -p \
  /code/ai_services_api/services/search/models \
  /code/logs \
  /code/cache \
  /opt/airflow/logs \
  /opt/airflow/dags \
  /opt/airflow/plugins \
  /opt/airflow/data

# Set permissions for both app and airflow directories
RUN chown -R appuser:appgroup /code && \
    chown -R appuser:appgroup /opt/airflow && \
    chmod -R 775 /code && \
    chmod -R 775 /opt/airflow

WORKDIR /code

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --chown=appuser:appgroup . .

RUN chmod +x /code/scripts/init-script.sh

ENV TRANSFORMERS_CACHE=/code/cache \
    HF_HOME=/code/cache

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

USER appuser
