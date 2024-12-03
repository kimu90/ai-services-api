import os
import psycopg2
from psycopg2 import sql
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

def get_db_connection():
    """Create a connection to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('POSTGRES_DB', 'aphrc'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'p0stgres'),
            host=os.getenv('POSTGRES_HOST', '167.86.85.127'),
            port=os.getenv('POSTGRES_PORT', '5432')
        )
        conn.autocommit = False  # Ensure explicit transaction management
        logger.info("Successfully connected to database")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Error connecting to the database: {e}")
        raise

class DatabaseManager:
    def __init__(self):
        """Initialize DatabaseManager with connection."""
        try:
            self.conn = get_db_connection()
            logger.info("DatabaseManager initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing DatabaseManager: {e}")
            raise

    def _ensure_connection(self):
        """Ensure database connection is alive and reset if needed"""
        try:
            if self.conn.closed or self.conn.status != psycopg2.extensions.STATUS_READY:
                logger.warning("Database connection lost - attempting to reconnect")
                if not self.conn.closed:
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                self.conn = get_db_connection()
        except Exception as e:
            logger.error(f"Error checking connection status: {e}")
            self.conn = get_db_connection()

    def get_matching_queries(self, partial_query: str, expert_id: Optional[int] = None, limit: int = 5) -> List[str]:
        """Get matching previous queries including duplicates"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                if expert_id:
                    # Get queries for specific expert
                    cur.execute("""
                        WITH RankedQueries AS (
                            SELECT 
                                query,
                                COUNT(*) as frequency,
                                MAX(timestamp) as last_used
                            FROM query_history 
                            WHERE query ILIKE %s AND expert_id = %s
                            GROUP BY query
                        )
                        SELECT query
                        FROM RankedQueries
                        ORDER BY frequency DESC, last_used DESC
                        LIMIT %s
                    """, (f"{partial_query}%", expert_id, limit))
                else:
                    # Get queries across all experts
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
                self.conn.commit()
                return results
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting matching queries: {e}")
            return []

    def add_query(self, query: str, expert_id: Optional[int] = None, result_count: int = 0, 
                 search_type: str = 'semantic'):
        """Add a query to the history"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO query_history (query, expert_id, result_count, search_type, timestamp)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    RETURNING query_id
                """, (query, expert_id, result_count, search_type))
                
                query_id = cur.fetchone()[0]
                
                # Update term frequencies
                terms = query.lower().split()
                for term in terms:
                    cur.execute("""
                        INSERT INTO term_frequencies (term, frequency, expert_id, last_updated)
                        VALUES (%s, 1, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (term) 
                        DO UPDATE SET 
                            frequency = term_frequencies.frequency + 1,
                            last_updated = CURRENT_TIMESTAMP
                    """, (term, expert_id))
                
                self.conn.commit()
                return query_id
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding query to history: {e}")
            return None

    def get_term_frequencies(self, expert_id: Optional[int] = None) -> Dict[str, int]:
        """Get term frequency dictionary"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                if expert_id:
                    cur.execute("""
                        SELECT term, frequency 
                        FROM term_frequencies 
                        WHERE expert_id = %s AND last_updated >= NOW() - INTERVAL '30 days'
                    """, (expert_id,))
                else:
                    cur.execute("""
                        SELECT term, SUM(frequency) as total_frequency
                        FROM term_frequencies 
                        WHERE last_updated >= NOW() - INTERVAL '30 days'
                        GROUP BY term
                    """)
                results = dict(cur.fetchall())
                self.conn.commit()
                return results
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting term frequencies: {e}")
            return {}

    def get_popular_queries(self, expert_id: Optional[int] = None, limit: int = 10, 
                          days: int = 30) -> List[dict]:
        """Get most frequent queries within the specified time period"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                if expert_id:
                    cur.execute("""
                        SELECT query, COUNT(*) as count
                        FROM query_history
                        WHERE timestamp >= NOW() - INTERVAL %s DAY AND expert_id = %s
                        GROUP BY query
                        ORDER BY count DESC
                        LIMIT %s
                    """, (days, expert_id, limit))
                else:
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

    def get_recent_queries(self, expert_id: Optional[int] = None, limit: int = 10) -> List[dict]:
        """Get most recent unique queries"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                if expert_id:
                    cur.execute("""
                        SELECT DISTINCT ON (query) 
                            query, 
                            timestamp,
                            result_count,
                            expert_id
                        FROM query_history
                        WHERE expert_id = %s
                        ORDER BY query, timestamp DESC
                        LIMIT %s
                    """, (expert_id, limit))
                else:
                    cur.execute("""
                        SELECT DISTINCT ON (query) 
                            query, 
                            timestamp,
                            result_count,
                            expert_id
                        FROM query_history
                        ORDER BY query, timestamp DESC
                        LIMIT %s
                    """, (limit,))
                results = [{
                    'query': row[0], 
                    'timestamp': row[1],
                    'result_count': row[2],
                    'expert_id': row[3]
                } for row in cur.fetchall()]
                self.conn.commit()
                return results
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error getting recent queries: {e}")
            return []

    def get_query_timestamps(self, query: str, expert_id: Optional[int] = None, 
                           limit: int = 10) -> List[datetime]:
        """Get timestamps for a specific query"""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                if expert_id:
                    cur.execute("""
                        SELECT timestamp 
                        FROM query_history 
                        WHERE query = %s AND expert_id = %s
                        ORDER BY timestamp DESC 
                        LIMIT %s
                    """, (query, expert_id, limit))
                else:
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