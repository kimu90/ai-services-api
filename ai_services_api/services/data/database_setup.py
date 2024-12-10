import os
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
import logging
import json
import secrets
import string
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

def get_connection_params():
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        parsed_url = urlparse(database_url)
        return {'host': parsed_url.hostname, 'port': parsed_url.port, 'dbname': parsed_url.path[1:],
                'user': parsed_url.username, 'password': parsed_url.password}
    else:
        in_docker = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
        return {'host': '167.86.85.127' if in_docker else 'localhost', 'port': '5432',
                'dbname': os.getenv('POSTGRES_DB', 'aphrc'), 'user': os.getenv('POSTGRES_USER', 'postgres'),
                'password': os.getenv('POSTGRES_PASSWORD', 'p0stgres')}

def get_db_connection(dbname=None):
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
    params = get_connection_params()
    target_dbname = params['dbname']
    try:
        try:
            conn = get_db_connection()
            logger.info(f"Database {target_dbname} already exists")
            conn.close()
            return
        except psycopg2.OperationalError:
            pass
        conn = get_db_connection('postgres')
        conn.autocommit = True
        cur = conn.cursor()
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

def generate_fake_password():
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

def fix_experts_table():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'experts_expert');")
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            # Original columns to add
            columns_to_add = [
                ('firstname', 'VARCHAR(255)'),
                ('lastname', 'VARCHAR(255)'),
                ('designation', 'VARCHAR(255)'),
                ('theme', 'VARCHAR(255)'),
                ('unit', 'VARCHAR(255)'),
                ('contact_details', 'VARCHAR(255)'),
                ('knowledge_expertise', 'JSONB'),
                ('orcid', 'VARCHAR(255)'),
                ('domains', 'JSONB'),
                ('fields', 'JSONB'),
                ('subfields', 'JSONB')
            ]
            
            # Add normalized expertise columns
            cur.execute("""
                ALTER TABLE experts_expert
                ADD COLUMN IF NOT EXISTS normalized_domains text[] DEFAULT '{}',
                ADD COLUMN IF NOT EXISTS normalized_fields text[] DEFAULT '{}',
                ADD COLUMN IF NOT EXISTS normalized_skills text[] DEFAULT '{}',
                ADD COLUMN IF NOT EXISTS keywords text[] DEFAULT '{}',
                ADD COLUMN IF NOT EXISTS search_text text,
                ADD COLUMN IF NOT EXISTS last_updated timestamp with time zone DEFAULT NOW();
            """)
            logger.info("Added normalized expertise columns")

            # Create function to update search_text
            cur.execute("""
                CREATE OR REPLACE FUNCTION update_expert_search_text()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.search_text = 
                        COALESCE(NEW.knowledge_expertise::text, '') || ' ' ||
                        COALESCE(array_to_string(NEW.normalized_domains, ' '), '') || ' ' ||
                        COALESCE(array_to_string(NEW.normalized_fields, ' '), '') || ' ' ||
                        COALESCE(array_to_string(NEW.normalized_skills, ' '), '');
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)
            logger.info("Created search text update function")

            # Create trigger
            cur.execute("""
                DROP TRIGGER IF EXISTS expert_search_text_trigger ON experts_expert;
                CREATE TRIGGER expert_search_text_trigger
                BEFORE INSERT OR UPDATE ON experts_expert
                FOR EACH ROW
                EXECUTE FUNCTION update_expert_search_text();
            """)
            logger.info("Created search text update trigger")

            # Create GIN indexes for array columns
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_expert_domains ON experts_expert USING gin(normalized_domains);
                CREATE INDEX IF NOT EXISTS idx_expert_fields ON experts_expert USING gin(normalized_fields);
                CREATE INDEX IF NOT EXISTS idx_expert_skills ON experts_expert USING gin(normalized_skills);
                CREATE INDEX IF NOT EXISTS idx_expert_keywords ON experts_expert USING gin(keywords);
            """)
            logger.info("Created GIN indexes for array columns")

            # Create text search index
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_expert_search ON experts_expert USING gin(to_tsvector('english', COALESCE(search_text, '')));
            """)
            logger.info("Created text search index")

            # Update existing rows to populate search_text
            cur.execute("""
                UPDATE experts_expert SET last_updated = NOW();
            """)
            logger.info("Updated existing rows to trigger search text generation")

            # Add original columns if they don't exist
            for column_name, column_type in columns_to_add:
                cur.execute(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'experts_expert' AND column_name = %s
                    );
                """, (column_name,))
                column_exists = cur.fetchone()[0]
                if not column_exists:
                    cur.execute(f"ALTER TABLE experts_expert ADD COLUMN {column_name} {column_type};")
                    logger.info(f"Added '{column_name}' column to experts_expert table.")

            # Handle existing data
            cur.execute("""
                UPDATE experts_expert
                SET firstname = COALESCE(NULLIF(TRIM(firstname), ''), 'Unknown'),
                    lastname = COALESCE(NULLIF(TRIM(lastname), ''), 'Unknown')
                WHERE firstname IS NULL OR lastname IS NULL;
            """)

            # Handle duplicates
            cur.execute("""
                WITH duplicates AS (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY id) as row_num
                    FROM experts_expert
                    WHERE firstname = 'Unknown' AND lastname = 'Unknown'
                )
                UPDATE experts_expert
                SET lastname = lastname || ' ' || duplicates.row_num
                FROM duplicates
                WHERE experts_expert.id = duplicates.id AND duplicates.row_num > 1;
            """)
            logger.info("Updated duplicate 'Unknown' entries.")

            # Add unique constraint if it doesn't exist
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.table_constraints 
                    WHERE table_name = 'experts_expert' 
                    AND constraint_type = 'UNIQUE' 
                    AND constraint_name = 'experts_expert_firstname_lastname_key'
                );
            """)
            unique_constraint_exists = cur.fetchone()[0]
            if not unique_constraint_exists:
                cur.execute("""
                    ALTER TABLE experts_expert
                    ADD CONSTRAINT experts_expert_firstname_lastname_key UNIQUE (firstname, lastname);
                """)
                logger.info("Added unique constraint on firstname and lastname.")

            conn.commit()
            logger.info("Fixed experts_expert table structure and handled all columns and indexes.")
        else:
            logger.warning("experts_expert table does not exist. It will be created when needed.")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Error fixing experts_expert table: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS experts_expert (
                id SERIAL PRIMARY KEY,
                firstname VARCHAR(255) NOT NULL,
                lastname VARCHAR(255) NOT NULL,
                designation VARCHAR(255),
                theme VARCHAR(255),
                unit VARCHAR(255),
                contact_details VARCHAR(255),
                knowledge_expertise JSONB,
                orcid VARCHAR(255) UNIQUE,
                domains JSONB,
                fields JSONB,
                subfields JSONB,
                password VARCHAR(255) NOT NULL,
                UNIQUE (firstname, lastname)
            );
            CREATE TABLE IF NOT EXISTS resources_resource (
                doi VARCHAR(255) PRIMARY KEY,
                title TEXT NOT NULL,
                abstract TEXT,
                summary TEXT,
                authors TEXT[],
                description TEXT,
                expert_id INTEGER REFERENCES experts_expert(id)
            );
            CREATE TABLE IF NOT EXISTS tags (
                tag_id SERIAL PRIMARY KEY,
                tag_name VARCHAR(255) UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS query_history_ai (
                query_id SERIAL PRIMARY KEY,
                query TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                result_count INTEGER,
                search_type VARCHAR(50),
                user_id TEXT
            );
            CREATE TABLE IF NOT EXISTS term_frequencies (
                term VARCHAR(255),
                frequency INTEGER DEFAULT 1,
                expert_id INTEGER REFERENCES experts_expert(id),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (term)
            );
            CREATE INDEX IF NOT EXISTS idx_experts_name ON experts_expert (firstname, lastname);
            CREATE INDEX IF NOT EXISTS idx_query_history_timestamp ON query_history_ai (timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_query_history_user ON query_history_ai (user_id);
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

def load_initial_experts(expertise_csv: str):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        df = pd.read_csv(expertise_csv)
        for _, row in df.iterrows():
            firstname = row['Firstname']
            lastname = row['Lastname']
            designation = row['Designation']
            theme = row['Theme']
            unit = row['Unit']
            contact_details = row['Contact Details']
            expertise_str = row['Knowledge and Expertise']
            expertise_list = [exp.strip() for exp in expertise_str.split(',') if exp.strip()]
            fake_password = generate_fake_password()

            cur.execute("""
                INSERT INTO experts_expert (
                    firstname, lastname, designation, theme, unit, contact_details, 
                    knowledge_expertise, domains, fields, subfields, password
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (firstname, lastname) DO UPDATE
                SET designation = EXCLUDED.designation,
                    theme = EXCLUDED.theme,
                    unit = EXCLUDED.unit,
                    contact_details = EXCLUDED.contact_details,
                    knowledge_expertise = EXCLUDED.knowledge_expertise,
                    password = EXCLUDED.password
                RETURNING id
            """, (
                firstname, lastname, designation, theme, unit, contact_details,
                json.dumps(expertise_list), json.dumps([]), json.dumps([]), json.dumps([]),
                fake_password
            ))
            conn.commit()
            logger.info(f"Added/updated expert data for {firstname} {lastname}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error loading initial expert data: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_database_if_not_exists()
    create_tables()
    fix_experts_table()
    load_initial_experts('expertise.csv')