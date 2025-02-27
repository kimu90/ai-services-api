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
            'dbname': parsed_url.path[1:],
            'user': parsed_url.username,
            'password': parsed_url.password
        }
    else:
        return {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'dbname': os.getenv('POSTGRES_DB', 'aphrc'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'p0stgres')
        }

def get_db_connection(dbname=None):
    """Create a connection to PostgreSQL database."""
    params = get_connection_params()
    if dbname:
        params['dbname'] = dbname
    
    try:
        conn = psycopg2.connect(**params)
        conn.autocommit = True
        logger.info(f"Successfully connected to database: {params['dbname']} at {params['host']}")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Error connecting to the database: {e}")
        raise

def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    params = get_connection_params()
    target_dbname = params['dbname']
    
    try:
        # Try connecting to target database first
        try:
            conn = get_db_connection()
            logger.info(f"Database {target_dbname} already exists")
            conn.close()
            return
        except psycopg2.OperationalError:
            pass  # Database doesn't exist, continue with creation

        # Connect to default postgres database to create new database
        conn = get_db_connection('postgres')
        conn.autocommit = True
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_dbname,))
        if not cur.fetchone():
            logger.info(f"Creating database {target_dbname}...")
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_dbname)))
            logger.info(f"Database {target_dbname} created successfully")
        else:
            logger.info(f"Database {target_dbname} already exists")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def create_tables():
    """Create the aphrc_expertise table."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Create new aphrc_expertise table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS aphrc_expertise (
                id SERIAL PRIMARY KEY,
                first_name VARCHAR(255) NOT NULL,
                last_name VARCHAR(255) NOT NULL,
                designation VARCHAR(255),
                theme VARCHAR(255),
                unit VARCHAR(255),
                contact_details VARCHAR(255),
                expertise TEXT[],
                domains TEXT[],
                fields TEXT[],
                subfields TEXT[],
                orcid VARCHAR(255),
                UNIQUE (first_name, last_name)
            );

            -- Create indexes for efficient querying
            CREATE INDEX IF NOT EXISTS idx_aphrc_name 
            ON aphrc_expertise (first_name, last_name);
            
            CREATE INDEX IF NOT EXISTS idx_aphrc_theme
            ON aphrc_expertise (theme);
            
            CREATE INDEX IF NOT EXISTS idx_aphrc_unit
            ON aphrc_expertise (unit);
        """)
        
        conn.commit()
        logger.info("aphrc_expertise table created successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating tables: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_database_if_not_exists()
    create_tables()
