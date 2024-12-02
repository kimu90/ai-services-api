import os
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
import logging
from typing import List, Dict, Optional
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def get_connection_params():
    """Get database connection parameters from environment variables."""
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        parsed_url = urlparse(database_url)
        return {
            'host': parsed_url.hostname,
            'port': parsed_url.port,
            'dbname': parsed_url.path[1:],  # Remove leading '/'
            'user': parsed_url.username,
            'password': parsed_url.password
        }
    else:
        in_docker = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
        return {
            'host': 'postgres' if in_docker else 'localhost',
            'port': '5432',
            'dbname': os.getenv('POSTGRES_DB', 'aphrcdb'),
            'user': os.getenv('POSTGRES_USER', 'aphrcuser'),
            'password': os.getenv('POSTGRES_PASSWORD', 'kimu')
        }

def get_db_connection(dbname=None):
    """
    Create a connection to PostgreSQL database.
    If dbname is None, uses the configured database name.
    """
    params = get_connection_params()
    if dbname:
        params['dbname'] = dbname
        
    try:
        conn = psycopg2.connect(**params)
        conn.autocommit = False  # Ensure explicit transaction management
        logger.info(f"Successfully connected to database: {params['dbname']}")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Error connecting to the database: {e}")
        logger.error(f"Connection params (without password): {dict(params, password='*****')}")
        raise

class DatabaseManager:
    def __init__(self):
        """Initialize DatabaseManager with connection and create tables."""
        try:
            self.conn = get_db_connection()
            self._create_tables()
            logger.info("DatabaseManager initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing DatabaseManager: {e}")
            raise

    def _ensure_connection(self):
        """Ensure database connection is alive and reset if needed"""
        try:
            # Check if connection is closed or in error state
            if self.conn.closed or self.conn.status != psycopg2.extensions.STATUS_READY:
                logger.warning("Database connection lost - attempting to reconnect")
                if not self.conn.closed:
                    try:
                        self.conn.rollback()  # Try to rollback any pending transaction
                    except Exception:
                        pass
                self.conn = get_db_connection()
        except Exception as e:
            logger.error(f"Error checking connection status: {e}")
            self.conn = get_db_connection()

    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            with self.conn.cursor() as cur:
                # Create query history table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS query_history (
                        query_id SERIAL PRIMARY KEY,
                        query TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        result_count INT,
                        search_type VARCHAR(50)
                    )
                """)

                # Create term frequencies table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS term_frequencies (
                        term_id SERIAL PRIMARY KEY,
                        term TEXT NOT NULL UNIQUE,
                        frequency INTEGER DEFAULT 1,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create indices for better performance
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_query_history_query 
                    ON query_history (query text_pattern_ops)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_query_history_timestamp 
                    ON query_history (timestamp DESC)
                """)

                self.conn.commit()
                logger.info("Database tables created successfully")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating tables: {e}")
            raise

    def get_matching_queries(self, partial_query: str, limit: int = 5) -> List[str]:
        """Get matching previous queries including duplicates"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                # Using CTE for proper handling of timestamps and frequency
                cur.execute("""
                    WITH RankedQueries AS (
                        SELECT 
                            query,
                            COUNT(*) as frequency,
                            MAX(timestamp) as last_used
                        FROM query_history 
                        WHERE query ILIKE %s 
                        GROUP BY query
                    )
                    SELECT query
                    FROM RankedQueries
                    ORDER BY frequency DESC, last_used DESC
                    LIMIT %s
                """, (f"{partial_query}%", limit))
                
                results = [row[0] for row in cur.fetchall()]
                self.conn.commit()  # Commit to clear any pending transaction
                return results
                
        except Exception as e:
            self.conn.rollback()  # Rollback on error
            logger.error(f"Error getting matching queries: {e}")
            return []

    def add_query(self, query: str, result_count: int = 0, search_type: str = 'semantic'):
        """Add a query to the history"""
        try:
            self._ensure_connection()
            query_id = None
            with self.conn.cursor() as cur:
                # Store the query first
                cur.execute("""
                    INSERT INTO query_history (query, result_count, search_type)
                    VALUES (%s, %s, %s)
                    RETURNING query_id
                """, (query, result_count, search_type))
                
                # Fetch the result before committing
                query_id = cur.fetchone()[0]
                
                # Update term frequencies
                terms = query.lower().split()
                for term in terms:
                    cur.execute("""
                        INSERT INTO term_frequencies (term, frequency)
                        VALUES (%s, 1)
                        ON CONFLICT (term) 
                        DO UPDATE SET 
                            frequency = term_frequencies.frequency + 1,
                            last_updated = CURRENT_TIMESTAMP
                    """, (term,))
                
                self.conn.commit()
                return query_id
                
        except Exception as e:
            self.conn.rollback()  # Ensure we rollback on error
            logger.error(f"Error adding query to history: {e}")
            return None

    def get_term_frequencies(self) -> Dict[str, int]:
        """Get term frequency dictionary"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT term, frequency 
                    FROM term_frequencies 
                    WHERE last_updated >= NOW() - INTERVAL '30 days'
                """)
                results = dict(cur.fetchall())
                self.conn.commit()
                return results
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting term frequencies: {e}")
            return {}

    def get_popular_queries(self, limit: int = 10, days: int = 30) -> List[dict]:
        """Get most frequent queries within the specified time period"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT query, COUNT(*) as count
                    FROM query_history
                    WHERE timestamp >= NOW() - INTERVAL %s DAY
                    GROUP BY query
                    ORDER BY count DESC
                    LIMIT %s
                """, (days, limit))
                results = [{'query': row[0], 'count': row[1]} for row in cur.fetchall()]
                self.conn.commit()
                return results
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting popular queries: {e}")
            return []

    def get_recent_queries(self, limit: int = 10) -> List[dict]:
        """Get most recent unique queries"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT ON (query) 
                        query, 
                        timestamp,
                        result_count
                    FROM query_history
                    ORDER BY timestamp DESC, query
                    LIMIT %s
                """, (limit,))
                results = [{
                    'query': row[0], 
                    'timestamp': row[1],
                    'result_count': row[2]
                } for row in cur.fetchall()]
                self.conn.commit()
                return results
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting recent queries: {e}")
            return []

    def get_query_timestamps(self, query: str, limit: int = 10) -> List[datetime]:
        """Get timestamps for a specific query"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT timestamp 
                    FROM query_history 
                    WHERE query = %s 
                    ORDER BY timestamp DESC 
                    LIMIT %s
                """, (query, limit))
                results = [row[0] for row in cur.fetchall()]
                self.conn.commit()
                return results
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting query timestamps: {e}")
            return []

    def __del__(self):
        """Close the database connection when the object is destroyed"""
        if hasattr(self, 'conn') and self.conn and not self.conn.closed:
            try:
                self.conn.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")