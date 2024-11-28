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

# Install Poetry
RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false

# Copy only dependency files first
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-dev

# Install specific packages
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install sentence-transformers && \
    pip install faiss-cpu==1.9.0.post1

# Final Stage
FROM python:3.11-slim

# Install necessary runtime dependencies
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
    && chmod -R 777 /code/models /code/logs /code/cache

# Set working directory
WORKDIR /code

# Copy from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Set permissions for script and code directory
RUN chmod +x /code/init-script.sh && \
    chmod -R 777 /code

# Environment variables for caching and models
ENV TRANSFORMERS_CACHE=/code/cache \
    HF_HOME=/code/cache \
    MODEL_PATH=/code/models/search

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the initialization script
CMD ["/code/init-script.sh"]