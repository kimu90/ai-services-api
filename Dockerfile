FROM python:3.11

# Update and install necessary dependencies
RUN apt update && \
    apt install -y \
    postgresql \
    gcc \
    redis-tools  # Add redis-tools for redis-cli

# Upgrade pip to the latest version
RUN pip install --upgrade pip

# Install Poetry for dependency management
RUN pip install poetry

# Configure Poetry to not use virtual environments
RUN poetry config virtualenvs.create false

# Copy project files for Poetry
COPY pyproject.toml poetry.lock ./

# Install dependencies specified in the pyproject.toml and poetry.lock
RUN poetry install

# Copy the rest of the application code
COPY . .