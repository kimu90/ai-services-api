import os
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
import logging

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
        logger.info(f"Successfully connected to database: {params['dbname']}")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Error connecting to the database: {e}")
        logger.error(f"Connection params: {params}")
        raise

def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    params = get_connection_params()
    target_dbname = params['dbname']
    
    try:
        # First connect to 'postgres' database
        conn = get_db_connection('postgres')
        conn.autocommit = True
        cur = conn.cursor()

        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_dbname,))
        exists = cur.fetchone()
        
        if not exists:
            logger.info(f"Creating database {target_dbname}...")
            cur.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(target_dbname)
            ))
            logger.info(f"Database {target_dbname} created successfully")
        else:
            logger.info(f"Database {target_dbname} already exists")

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def create_tables():
    """Create the necessary database tables."""
    conn = get_db_connection()
    cur = conn.cursor()

    sql_statements = [
        # Core publication tables
        """
        CREATE TABLE IF NOT EXISTS publications (
            doi VARCHAR(255) PRIMARY KEY,
            title TEXT NOT NULL,
            abstract TEXT,
            summary TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS tags (
            tag_id SERIAL PRIMARY KEY,
            tag_name VARCHAR(255) NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS publication_tag (
            publication_doi VARCHAR(255) REFERENCES publications(doi) ON DELETE CASCADE,
            tag_id INT REFERENCES tags(tag_id) ON DELETE CASCADE,
            PRIMARY KEY (publication_doi, tag_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS authors (
            author_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            orcid VARCHAR(255),
            author_identifier VARCHAR(255),
            CONSTRAINT unique_author UNIQUE (name, orcid, author_identifier)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS author_publication (
            author_id INT REFERENCES authors(author_id) ON DELETE CASCADE,
            doi VARCHAR(255) REFERENCES publications(doi) ON DELETE CASCADE,
            PRIMARY KEY (author_id, doi)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS experts (
            orcid VARCHAR(255) PRIMARY KEY,
            firstname VARCHAR(255) NOT NULL,
            lastname VARCHAR(255) NOT NULL,
            domains TEXT[],
            fields TEXT[],
            subfields TEXT[]
        );
        """,
        
        # Search history tables
        """
        CREATE TABLE IF NOT EXISTS query_history (
            query_id SERIAL PRIMARY KEY,
            query TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            result_count INT,
            search_type VARCHAR(50)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS term_frequencies (
            term_id SERIAL PRIMARY KEY,
            term TEXT NOT NULL UNIQUE,
            frequency INTEGER DEFAULT 1,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        
        # Create indices for search tables
        """
        CREATE INDEX IF NOT EXISTS idx_query_history_query 
        ON query_history (query text_pattern_ops);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_query_history_timestamp 
        ON query_history (timestamp DESC);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_term_frequencies_term 
        ON term_frequencies (term);
        """
    ]

    try:
        for statement in sql_statements:
            cur.execute(statement)
        conn.commit()
        logger.info("All tables created successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating tables: {e}")
        raise

    finally:
        cur.close()
        conn.close()

def drop_all_tables():
    """Drop all tables in the database."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        tables = [
            'term_frequencies',
            'query_history',
            'experts', 
            'author_publication', 
            'authors', 
            'publication_tag', 
            'tags', 
            'publications'
        ]

        for table in tables:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        
        conn.commit()
        logger.info("All tables dropped successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error dropping tables: {e}")
        raise

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'drop':
        drop_all_tables()
    else:
        create_database_if_not_exists()
        create_tables()