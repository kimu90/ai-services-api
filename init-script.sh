#!/bin/bash

set -e
set -o pipefail

LOG_DIR="/code/logs"
HEALTH_LOG="$LOG_DIR/health_checks.log"
SERVICE_LOG="$LOG_DIR/services.log"
INIT_LOG="$LOG_DIR/initialization.log"
DEBUG_LOG="$LOG_DIR/debug.log"
INIT_MARKER_DIR="/code/.initialization_complete"
INIT_MARKER_FILE="$INIT_MARKER_DIR/init.complete"

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

# Function to check if a port is open
check_port() {
    local host=$1
    local port=$2
    timeout 5 bash -c "</dev/tcp/$host/$port" 2>/dev/null
    return $?
}

# Enhanced Redis check function with detailed diagnostics
check_redis() {
    local host=${1:-redis}
    local port=${2:-6379}
    local debug_info=""
    
    # First check if port is open using nc
    if nc -z -w5 "$host" "$port" 2>/dev/null; then
        log "DEBUG" "Port $port is open on $host"
    else
        debug_info="Port $port is not open on $host\n"
        echo -e "$debug_info" >> "$DEBUG_LOG"
        return 1
    fi
    
    # Try both socket and redis-cli approaches
    if redis-cli -h "$host" ping >/dev/null 2>&1; then
        log "DEBUG" "Redis ping successful using redis-cli"
        return 0
    fi

    # Fallback to raw socket if redis-cli fails
    if echo -e "PING\r\n" | nc "$host" "$port" | grep -q "+PONG"; then
        log "DEBUG" "Redis ping successful using netcat"
        return 0
    fi
    
    # If both methods fail, collect debug information
    debug_info="Redis connection failed. Debug information:\n"
    debug_info+="Redis CLI test: $(redis-cli -h "$host" ping 2>&1)\n"
    debug_info+="Network test: $(nc -v "$host" "$port" 2>&1)\n"
    debug_info+="Host resolution: $(getent hosts "$host" 2>&1)\n"
    
    if command -v dig >/dev/null 2>&1; then
        debug_info+="DNS lookup: $(dig +short "$host" 2>&1)\n"
    fi
    
    echo -e "$debug_info" >> "$DEBUG_LOG"
    return 1
}

# Enhanced PostgreSQL check function
check_postgres() {
    local host=${1:-postgres}
    local db=$POSTGRES_DB
    local user=$POSTGRES_USER
    local password=$POSTGRES_PASSWORD
    local debug_info=""
    
    if ! check_port "$host" 5432; then
        debug_info="PostgreSQL port 5432 is not open on $host\n"
        echo -e "$debug_info" >> "$DEBUG_LOG"
        return 1
    fi
    
    if PGPASSWORD=$password psql -h "$host" -U "$user" -d "$db" -c 'SELECT 1' >/dev/null 2>&1; then
        return 0
    else
        debug_info="PostgreSQL connection failed. Debug information:\n"
        debug_info+="Connection error: $(PGPASSWORD=$password psql -h "$host" -U "$user" -d "$db" -c 'SELECT 1' 2>&1)\n"
        echo -e "$debug_info" >> "$DEBUG_LOG"
        return 1
    fi
}

# Enhanced Neo4j check function
check_neo4j() {
    local host=${1:-neo4j}
    local debug_info=""
    
    if ! check_port "$host" 7474; then
        debug_info="Neo4j HTTP port 7474 is not open on $host\n"
        echo -e "$debug_info" >> "$DEBUG_LOG"
        return 1
    fi
    
    if ! check_port "$host" 7687; then
        debug_info="Neo4j Bolt port 7687 is not open on $host\n"
        echo -e "$debug_info" >> "$DEBUG_LOG"
        return 1
    fi
    
    local http_response
    http_response=$(curl -s -o /dev/null -w "%{http_code}" "http://$host:7474/browser/")
    if [ "$http_response" = "200" ]; then
        return 0
    else
        debug_info="Neo4j HTTP check failed. Response code: $http_response\n"
        echo -e "$debug_info" >> "$DEBUG_LOG"
        return 1
    fi
}

# Enhanced check_status function with logging
check_status() {
    local status=$?
    local message=$1
    if [ $status -eq 0 ]; then
        log "INFO" "✅ $message completed successfully"
    else
        log "ERROR" "❌ $message failed with exit code $status"
        log "DEBUG" "Last few lines of service logs:"
        tail -n 50 "$DEBUG_LOG" >> "$DEBUG_LOG"
        exit 1
    fi
}

# Enhanced wait_for_service function with detailed logging
wait_for_service() {
    local service=$1
    local check_command=$2
    local max_retries=$3
    local sleep_time=${4:-5}
    local counter=0
    
    log "HEALTH" "Starting health checks for $service"
    
    until eval "$check_command"; do
        counter=$((counter + 1))
        if [ $counter -eq $max_retries ]; then
            log "ERROR" "Failed to connect to $service after $max_retries attempts"
            log "DEBUG" "--- Begin $service diagnostics ---"
            case $service in
                "PostgreSQL")
                    log "DEBUG" "Running PostgreSQL diagnostics..."
                    check_postgres postgres >> "$DEBUG_LOG" 2>&1
                    ;;
                "Neo4j")
                    log "DEBUG" "Running Neo4j diagnostics..."
                    check_neo4j neo4j >> "$DEBUG_LOG" 2>&1
                    ;;
                "Redis")
                    log "DEBUG" "Running Redis diagnostics..."
                    check_redis redis >> "$DEBUG_LOG" 2>&1
                    ;;
            esac
            log "DEBUG" "--- End $service diagnostics ---"
            exit 1
        fi
        
        log "HEALTH" "Waiting for $service... (attempt $counter/$max_retries)"
        sleep "$sleep_time"
    done
    
    log "HEALTH" "$service is ready"
}

# Function to safely create initialization marker
create_init_marker() {
    log "INFO" "Creating initialization complete marker..."
    
    # Ensure parent directories exist with correct permissions
    if ! mkdir -p "$INIT_MARKER_DIR" 2>/dev/null; then
        log "WARNING" "Failed to create marker directory, trying alternate approach..."
        # Try to create with sudo if available
        if command -v sudo >/dev/null 2>&1; then
            if ! sudo mkdir -p "$INIT_MARKER_DIR"; then
                log "ERROR" "Failed to create initialization marker directory even with elevated privileges"
                return 1
            fi
            sudo chown -R "$(id -u):$(id -g)" "$INIT_MARKER_DIR"
        else
            log "ERROR" "Cannot create initialization marker directory"
            return 1
        fi
    fi
    
    # Try to create the marker file
    if ! echo "$(date '+%Y-%m-%d %H:%M:%S') - Initialization successful" > "$INIT_MARKER_FILE" 2>/dev/null; then
        log "ERROR" "Failed to create initialization marker file"
        return 1
    fi
    
    # Verify the file was created
    if [ -f "$INIT_MARKER_FILE" ]; then
        log "INFO" "Successfully created initialization marker"
        return 0
    else
        log "ERROR" "Initialization marker file not found after creation attempt"
        return 1
    fi
}

main() {
    # Check if initialization is already complete
    if [ -f "$INIT_MARKER_FILE" ]; then
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

    # Service checks
    log "SERVICE" "Starting service health checks"
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

    # Create initialization marker
    if ! create_init_marker; then
        log "ERROR" "Failed to create initialization marker"
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
