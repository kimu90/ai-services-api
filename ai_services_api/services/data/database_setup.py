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
        in_docker = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
        return {
            'host': '167.86.85.127' if in_docker else 'localhost',
            'port': '5432',
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

def fix_experts_table():
    """Fix the experts_expert table structure and handle duplicates."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'experts_expert'
            );
        """)
        table_exists = cur.fetchone()[0]

        if table_exists:
            # Check if the unique constraint already exists
            cur.execute("""
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE conname = 'experts_expert_firstname_lastname_key';
            """)
            constraint_exists = cur.fetchone()[0] > 0

            if not constraint_exists:
                # Step 1: Create a temporary table with the new structure
                cur.execute("""
                    CREATE TEMP TABLE experts_expert_temp (
                        id SERIAL PRIMARY KEY,
                        firstname VARCHAR(255) NOT NULL,
                        lastname VARCHAR(255) NOT NULL,
                        orcid VARCHAR(255) UNIQUE,
                        knowledge_expertise TEXT[],
                        domains TEXT[],
                        fields TEXT[],
                        subfields TEXT[],
                        UNIQUE (firstname, lastname)
                    );
                """)

                # Step 2: Insert data into temp table, handling duplicates by merging
                cur.execute("""
                    INSERT INTO experts_expert_temp (firstname, lastname, orcid, knowledge_expertise, domains, fields, subfields)
                    SELECT 
                        firstname,
                        lastname,
                        MAX(orcid) as orcid,
                        array_agg(DISTINCT unnest(knowledge_expertise)) FILTER (WHERE knowledge_expertise IS NOT NULL) as knowledge_expertise,
                        array_agg(DISTINCT unnest(domains)) FILTER (WHERE domains IS NOT NULL) as domains,
                        array_agg(DISTINCT unnest(fields)) FILTER (WHERE fields IS NOT NULL) as fields,
                        array_agg(DISTINCT unnest(subfields)) FILTER (WHERE subfields IS NOT NULL) as subfields
                    FROM experts_expert
                    GROUP BY firstname, lastname;
                """)

                # Step 3: Drop the old table
                cur.execute("DROP TABLE experts_expert CASCADE;")

                # Step 4: Rename temp table to original name
                cur.execute("""
                    ALTER TABLE experts_expert_temp 
                    RENAME TO experts_expert;
                """)

                # Step 5: Recreate indexes
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_experts_name 
                    ON experts_expert (firstname, lastname);
                """)

        conn.commit()
        logger.info("Successfully fixed experts_expert table structure")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error fixing experts_expert table: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def create_tables():
    """Create all required tables."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # First create UUID extension if needed
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        
        # Create tables
        cur.execute("""
            -- Create experts table
            CREATE TABLE IF NOT EXISTS experts_expert (
                id SERIAL PRIMARY KEY,
                firstname VARCHAR(255) NOT NULL,
                lastname VARCHAR(255) NOT NULL,
                orcid VARCHAR(255) UNIQUE,
                knowledge_expertise TEXT[],
                domains TEXT[],
                fields TEXT[],
                subfields TEXT[],
                UNIQUE (firstname, lastname)
            );

            -- Create resources table
            CREATE TABLE IF NOT EXISTS resources_resource (
                doi VARCHAR(255) PRIMARY KEY,
                title TEXT NOT NULL,
                abstract TEXT,
                summary TEXT,
                authors TEXT[],
                description TEXT,
                expert_id INTEGER REFERENCES experts_expert(id)
            );

            -- Create tags table
            CREATE TABLE IF NOT EXISTS tags (
                tag_id SERIAL PRIMARY KEY,
                tag_name VARCHAR(255) UNIQUE NOT NULL
            );

            -- Create query history table
            CREATE TABLE IF NOT EXISTS query_history_ai (
                query_id SERIAL PRIMARY KEY,
                query TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                result_count INTEGER,
                search_type VARCHAR(50),
                user_id TEXT
            );

            -- Create term frequencies table
            CREATE TABLE IF NOT EXISTS term_frequencies (
                term VARCHAR(255),
                frequency INTEGER DEFAULT 1,
                expert_id INTEGER REFERENCES experts_expert(id),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (term)
            );

            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_experts_name 
            ON experts_expert (firstname, lastname);
            
            CREATE INDEX IF NOT EXISTS idx_query_history_timestamp
            ON query_history_ai (timestamp DESC);
            
            CREATE INDEX IF NOT EXISTS idx_query_history_user
            ON query_history_ai (user_id);
        """)
        
        conn.commit()
        logger.info("All tables created successfully")
        
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
    fix_experts_table()