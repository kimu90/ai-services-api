#!/bin/bash

set -e

# Environment setup
INIT_MARKER="/code/.initialization_complete/init.done"
LOG_DIR="/code/logs"
mkdir -p "$LOG_DIR" "/code/.initialization_complete"

# Logging setup
exec 1> >(tee -a "${LOG_DIR}/init.log") 2>&1
echo "[$(date)] Starting initialization..."

# Function to check services
check_service() {
    local service=$1
    local host=$2
    local port=$3
    local max_attempts=$4
    local attempt=0
    
    echo "[$(date)] Checking $service..."
    until nc -z "$host" "$port" >/dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ $attempt -eq $max_attempts ]; then
            echo "[$(date)] ERROR: $service not available after $max_attempts attempts"
            return 1
        fi
        echo "[$(date)] Waiting for $service... (attempt $attempt/$max_attempts)"
        sleep 5
    done
    echo "[$(date)] $service is available"
}

# Function to initialize app
initialize_app() {
    if [ -f "$INIT_MARKER" ]; then
        echo "[$(date)] System already initialized"
        return 0
    fi
    
    # Check dependencies
    check_service "PostgreSQL" "postgres" 5432 30
    check_service "Redis" "redis" 6379 30
    check_service "Neo4j" "neo4j" 7687 30
    
    echo "[$(date)] Running database setup..."
    python -m setup
    
    echo "[$(date)] Creating search index..."
    python -m ai_services_api.services.search.index_creator
    
    echo "[$(date)] Creating Redis embeddings..."
    python -m ai_services_api.services.search.redis_embeddings
    
    # Create initialization marker
    date > "$INIT_MARKER"
    echo "[$(date)] Initialization complete"
}

# Main execution
if initialize_app; then
    echo "[$(date)] Starting application..."
    exec uvicorn ai_services_api.main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "[$(date)] Initialization failed!"
    exit 1
fi