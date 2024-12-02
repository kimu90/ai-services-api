#!/bin/bash

# Exit on any error and enable variable printing for debugging
set -e
set -o pipefail

# Define log directory structure
LOG_DIR="/code/logs"
HEALTH_LOG="$LOG_DIR/health_checks.log"
SERVICE_LOG="$LOG_DIR/services.log"
INIT_LOG="$LOG_DIR/initialization.log"
DEBUG_LOG="$LOG_DIR/debug.log"

# Enhanced logging function with timestamps and multiple outputs
log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Write to main log and console with color coding
    case $level in
        "ERROR")
            echo -e "[$timestamp] [\033[0;31m$level\033[0m] $message" | tee -a "$INIT_LOG"
            ;;
        "WARNING")
            echo -e "[$timestamp] [\033[0;33m$level\033[0m] $message" | tee -a "$INIT_LOG"
            ;;
        "INFO")
            echo -e "[$timestamp] [\033[0;32m$level\033[0m] $message" | tee -a "$INIT_LOG"
            ;;
        *)
            echo "[$timestamp] [$level] $message" | tee -a "$INIT_LOG"
            ;;
    esac
    
    # Log to specific files based on message type
    case $level in
        "DEBUG")
            echo "[$timestamp] $message" >> "$DEBUG_LOG"
            ;;
        "HEALTH")
            echo "[$timestamp] $message" >> "$HEALTH_LOG"
            ;;
        "SERVICE")
            echo "[$timestamp] $message" >> "$SERVICE_LOG"
            ;;
    esac
}

# [Other functions remain unchanged for brevity: check_port, check_redis, check_postgres, check_neo4j, check_status, wait_for_service]

# Main execution starts here
main() {
    # Check if initialization is already complete
    if [ -f /code/.initialization_complete ]; then
        log "INFO" "Previous initialization detected. Starting application..."
        exec uvicorn ai_services_api.main:app --host 0.0.0.0 --port 8000 --reload
        return
    fi

    # Create necessary directories
    mkdir -p "$LOG_DIR" /code/models/search /code/cache
    touch "$HEALTH_LOG" "$SERVICE_LOG" "$INIT_LOG" "$DEBUG_LOG"
    chmod -R 755 /code/models /code/logs /code/cache

    # Start initialization
    log "INFO" "Starting initialization process at $(date)"
    log "INFO" "Creating necessary directories..."
    check_status "Directory creation"

    # Wait for services with enhanced logging
    log "SERVICE" "Starting service health checks"

    # Service checks
    log "SERVICE" "Checking PostgreSQL..."
    wait_for_service "PostgreSQL" "check_postgres postgres" 90 10

    log "SERVICE" "Checking Neo4j..."
    wait_for_service "Neo4j" "check_neo4j neo4j" 90 10

    log "SERVICE" "Checking Redis..."
    wait_for_service "Redis" "check_redis redis" 90 10

    # Initialize database with logging
    log "INFO" "Initializing database and loading data..."
    max_retries=3
    counter=0
    until python -m setup --reset --publications 200; do
        counter=$((counter + 1))
        if [ $counter -eq $max_retries ]; then
            log "ERROR" "Failed to initialize database after $max_retries attempts"
            exit 1
        fi
        log "INFO" "Retrying database initialization... (attempt $counter/$max_retries)"
        sleep 10
    done
    check_status "Database initialization and data loading"

    # Initialize search index with logging
    log "INFO" "Creating search index..."
    counter=0
    until python -m ai_services_api.services.search.index_creator; do
        counter=$((counter + 1))
        if [ $counter -eq $max_retries ]; then
            log "ERROR" "Failed to create search index after $max_retries attempts"
            exit 1
        fi
        log "INFO" "Retrying search index creation... (attempt $counter/$max_retries)"
        sleep 8
    done
    check_status "Search index creation"

    # Final status checks
    log "INFO" "Running final status checks..."
    services_status=0

    if ! check_redis redis; then
        log "WARNING" "⚠️ Warning: Redis is not responding properly"
        services_status=1
    fi

    if ! check_postgres postgres; then
        log "WARNING" "⚠️ Warning: PostgreSQL is not responding properly"
        services_status=1
    fi

    if ! check_neo4j neo4j; then
        log "WARNING" "⚠️ Warning: Neo4j is not responding properly"
        services_status=1
    fi

    if [ $services_status -eq 0 ]; then
        log "INFO" "All services are running properly"
    else
        log "WARNING" "Some services are not responding properly"
    fi

    log "INFO" "Creating initialization complete marker..."
    TEMP_FILE=$(mktemp)
    if echo "$(date '+%Y-%m-%d %H:%M:%S') - Initialization successful" > "$TEMP_FILE"; then
        if mv "$TEMP_FILE" /code/.initialization_complete; then
            log "INFO" "Successfully created initialization marker"
        else
            log "ERROR" "Failed to move initialization marker to final location"
            rm -f "$TEMP_FILE"
            exit 1
        fi
    else
        log "ERROR" "Failed to create temporary initialization marker"
        rm -f "$TEMP_FILE"
        exit 1
    fi

    log "INFO" "Initialization completed at $(date)"

    # Start the FastAPI application
    log "INFO" "Starting FastAPI application..."
    if command -v uvicorn >/dev/null 2>&1; then
        log "INFO" "Starting server on port 8000..."
        exec uvicorn ai_services_api.main:app --host 0.0.0.0 --port 8000 --reload
    else
        log "ERROR" "uvicorn not found. Please ensure it is installed."
        exit 1
    fi
}

# Execute main function
main
