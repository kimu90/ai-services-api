# Optimize build with multi-stage build
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    python3-dev \
    libomp-dev \
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

# Final stage
FROM python:3.11-slim

# Install necessary runtime dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libomp-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /code/ai_services_api/services/search/models

# Set working directory
WORKDIR /code

# Copy from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Set permissions for init script
RUN chmod +x /code/init-script.sh

# Command to run the initialization script
CMD ["/code/init-script.sh"]
