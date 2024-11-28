# Builder Stage
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    libpq-dev \
    gcc \
    python3-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry and dependencies in one step for better layer caching
RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false

# Copy dependency files first (for caching)
COPY pyproject.toml poetry.lock ./

# Install dependencies without development dependencies
RUN poetry install --no-dev

# Install specific packages
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install sentence-transformers && \
    pip install faiss-cpu==1.9.0.post1

# Final Stage
FROM python:3.11-slim

# Install necessary runtime dependencies in a single step
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libomp-dev \
    curl \
    redis-tools \
    netcat-openbsd \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories with proper permissions
RUN mkdir -p /code/ai_services_api/services/search/models \
    /code/models \
    /code/logs \
    /code/cache \
    && chmod -R 775 /code/models /code/logs /code/cache

# Create a non-root user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser && \
    chown -R appuser:appgroup /code

# Set working directory
WORKDIR /code

# Copy files from builder stage in one step to minimize layers
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code with proper ownership directly
COPY --chown=appuser:appgroup . .

# Set permissions for scripts and files
RUN chmod +x /code/init-script.sh

# Environment variables for caching and models
ENV TRANSFORMERS_CACHE=/code/cache \
    HF_HOME=/code/cache \
    MODEL_PATH=/code/models/search

# Health check for application readiness
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER appuser

# Command to run the initialization script
CMD ["/code/init-script.sh"]
