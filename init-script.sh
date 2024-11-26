#!/bin/bash

# Set up error handling
set -euo pipefail  # Exit on errors, unset variables, and pipe failures

# Set PYTHONPATH for all scripts
export PYTHONPATH="/code"

# Log initialization start time
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting initialization..."

# Define base directories
BASE_DIR="/code"
SERVICES_DIR="${BASE_DIR}/ai_services_api/services"
SEARCH_DIR="${SERVICES_DIR}/search"
MODELS_DIR="${SEARCH_DIR}/models"

# Create necessary directories
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Creating directory structure..."
mkdir -p "${MODELS_DIR}"

# Function to wait for PostgreSQL to be ready
wait_for_postgres() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Waiting for PostgreSQL..."

    # Loop until PostgreSQL is available
    until PGPASSWORD="$POSTGRES_PASSWORD" psql -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] PostgreSQL is unavailable - sleeping"
        sleep 1
    done

    # Notify when PostgreSQL is available
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] PostgreSQL is available"
}

# Function to run a script with retry logic
run_with_retry() {
    local script=$1
    local max_attempts=3
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Attempting to run $script (attempt $attempt/$max_attempts)"

        # Attempt to run the script
        if python "$script"; then
            echo "[$(date +'%Y-%m-%d %H:%M:%S')] $script completed successfully"
            return 0  # Exit successfully if the script runs
        else
            echo "[$(date +'%Y-%m-%d %H:%M:%S')] $script failed on attempt $attempt"

            # Retry after a delay if the script fails
            if [ $attempt -eq $max_attempts ]; then
                echo "[$(date +'%Y-%m-%d %H:%M:%S')] All attempts failed for $script"
                exit 1  # Exit on failure after all retries
            fi

            # Exponentially increase sleep time between retries
            sleep $((attempt * 2))
            attempt=$((attempt + 1))
        fi
    done
}

# Main initialization sequence
main() {
    # Wait for PostgreSQL to be ready
    wait_for_postgres

    # Create database schema
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Creating database schema..."
    run_with_retry "${BASE_DIR}/Centralized-Repository/Database/create_database.py"

    # Process APHRC data
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Processing APHRC data..."
    run_with_retry "${BASE_DIR}/Centralized-Repository/aphrc_limit.py"

    # Create search index
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Creating search index..."
    run_with_retry "${BASE_DIR}/ai_services_api/services/search/index_creator.py"

    # Verify the index was created
    if [ ! -f "${MODELS_DIR}/faiss_index.idx" ]; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Error: Index file not created"
        exit 1  # Exit if the index file is not created
    fi

    # Start the API server
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting API server..."
    exec poetry run uvicorn ai_services_api.app:app --host 0.0.0.0 --port 8000 --reload
}

# Run the main initialization sequence
main
