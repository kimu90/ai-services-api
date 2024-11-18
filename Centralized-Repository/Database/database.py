import os
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse

def get_db_connection():
    """
    Create a connection to PostgreSQL database using environment variables,
    with fallback support for local development or Docker environments.
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
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to the database: {e}")
        print("\nConnection Details:")
        print(f"Database: {dbname}")
        print(f"User: {user}")
        print(f"Host: {host}")
        print(f"Port: {port}")
        raise

def create_tables():
    """
    Create the necessary database tables if they don't exist.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Create Publications Table
    create_publications_table = """
    CREATE TABLE IF NOT EXISTS publications (
        doi VARCHAR(255) PRIMARY KEY,         -- Unique Identifier for the publication
        title TEXT NOT NULL,                  -- Title of the publication
        abstract TEXT,                        -- Abstract of the publication
        summary TEXT,                         -- Summary of the publication
        link TEXT                             -- Link to the publication
    );
    """
    
    # Create Tags Table
    create_tags_table = """
    CREATE TABLE IF NOT EXISTS tags (
        tag_id SERIAL PRIMARY KEY,        -- Unique tag identifier
        tag_name VARCHAR(255) NOT NULL,   -- Name of the tag
        description TEXT,                 -- Optional description for the tag
        category TEXT                     -- Optional category to organize tags (e.g., Research, Methodology)
    );
    """
    
    # Create Publication_Tag Mapping Table
    create_publication_tag_table = """
    CREATE TABLE IF NOT EXISTS publication_tag (
        publication_doi VARCHAR(255) REFERENCES publications(doi) ON DELETE CASCADE,  -- Foreign key to publications
        tag_id INT REFERENCES tags(tag_id) ON DELETE CASCADE,                        -- Foreign key to tags
        PRIMARY KEY (publication_doi, tag_id)                                         -- Composite primary key
    );
    """
    
    # Create Authors Table with Name, ORCID, Author ID and Unique Constraint
    create_authors_table = """
    CREATE TABLE IF NOT EXISTS authors (
        author_id SERIAL PRIMARY KEY,         -- A system-generated unique ID for internal reference
        name TEXT NOT NULL,                   -- Author's full name (required)
        orcid VARCHAR(255),                   -- ORCID identifier (optional)
        author_identifier VARCHAR(255),       -- Author ID (optional)
        domain TEXT,                          -- Domain or field of expertise
        fields TEXT[],                        -- Array of fields of expertise
        subfields TEXT[],                     -- Array of subfields of expertise
        CONSTRAINT unique_author UNIQUE (name, orcid, author_identifier)
    );
    """
    
    # Create Author_Publication Mapping Table
    create_author_publication_table = """
    CREATE TABLE IF NOT EXISTS author_publication (
        author_id INT REFERENCES authors(author_id) ON DELETE CASCADE,  
        doi VARCHAR(255) REFERENCES publications(doi) ON DELETE CASCADE,
        PRIMARY KEY (author_id, doi)
    );
    """

    try:
        # Create the tables
        cur.execute(create_publications_table)
        cur.execute(create_tags_table)
        cur.execute(create_publication_tag_table)
        cur.execute(create_authors_table)
        cur.execute(create_author_publication_table)

        # Commit the changes
        conn.commit()
        print("Tables created successfully.")

    except Exception as e:
        print(f"Error creating tables: {e}")
        conn.rollback()
        raise

    finally:
        # Close the cursor and connection
        cur.close()
        conn.close()

if __name__ == "__main__":
    try:
        create_tables()
        print("Database setup completed successfully!")
    except Exception as e:
        print(f"\nFailed to set up database. Please check the following:")
        print("1. Is PostgreSQL running?")
        print("2. Are the database credentials correct?")
        print("3. Is the database accessible from your current environment?")
        print("\nFor local development, make sure:")
        print("- PostgreSQL is running on localhost:5432")
        print("- The database 'aphrcdb' exists")
        print("- The user 'aphrcuser' exists with the correct password")
        print("\nTo create the database and user manually, run these commands in PostgreSQL:")
        print(""" 
    CREATE DATABASE aphrcdb;
    CREATE USER aphrcuser WITH PASSWORD 'kimu';
    GRANT ALL PRIVILEGES ON DATABASE aphrcdb TO aphrcuser;
    """)
