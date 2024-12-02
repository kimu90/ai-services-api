import os
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """
    Create a connection to PostgreSQL database with robust configuration.
    Supports both DATABASE_URL and environment variable configurations.
    """
    # Check if we're running in Docker
    in_docker = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
    
    # Use DATABASE_URL if provided, else fallback to environment variables
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        parsed_url = urlparse(database_url)
        host = parsed_url.hostname
        port = parsed_url.port
        dbname = parsed_url.path[1:]  # Removing the leading '/'
        user = parsed_url.username
        password = parsed_url.password
    else:
        # Fallback to environment variables for local or Docker development
        host = 'postgres' if in_docker else 'localhost'
        port = '5432'
        dbname = os.getenv('POSTGRES_DB', 'aphrcdb')
        user = os.getenv('POSTGRES_USER', 'aphrcuser')
        password = os.getenv('POSTGRES_PASSWORD', 'kimu')

    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        logger.info(f"Successfully connected to database: {dbname}")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Error connecting to the database: {e}")
        logger.error("\nConnection Details:")
        logger.error(f"Database: {dbname}")
        logger.error(f"User: {user}")
        logger.error(f"Host: {host}")
        logger.error(f"Port: {port}")
        raise

def create_tables():
    """
    Create the necessary database tables with comprehensive error handling.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Table creation SQL statements (combine from your previous schema)
    sql_statements = [
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
        """
    ]

    try:
        # Execute each table creation statement
        for statement in sql_statements:
            cur.execute(statement)

        # Commit the changes
        conn.commit()
        logger.info("All tables created successfully.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating tables: {e}")
        raise

    finally:
        # Close the cursor and connection
        cur.close()
        conn.close()

def drop_all_tables():
    """
    Drop all tables in the database. USE WITH CAUTION.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # List of tables to drop
        tables = [
            'experts', 
            'author_publication', 
            'authors', 
            'publication_tag', 
            'tags', 
            'publications'
        ]

        # Drop tables with CASCADE to remove dependencies
        for table in tables:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        
        conn.commit()
        logger.info("All tables dropped successfully.")

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
        create_tables()