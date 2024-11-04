# Base Python image
FROM python:3.11-slim

# Install system dependencies including PostgreSQL client and build tools
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml poetry.lock ./
COPY . .

# Install Poetry
RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

# Install torch (CPU-only) and sentence-transformers directly using pip
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install sentence-transformers

# Command to run the application with Uvicorn
CMD ["uvicorn", "ai_services_api.app:app", "--host", "0.0.0.0", "--port", "8000"]