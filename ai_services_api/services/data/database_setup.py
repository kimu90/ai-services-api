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
    conn.autocommit = True  # Switch to autocommit mode
    cur = conn.cursor()
    
    try:
        # Check if table exists
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'experts_expert');")
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            # Define all column alterations
            alterations = [
                "ADD COLUMN IF NOT EXISTS normalized_domains text[] DEFAULT '{}'",
                "ADD COLUMN IF NOT EXISTS normalized_fields text[] DEFAULT '{}'",
                "ADD COLUMN IF NOT EXISTS normalized_skills text[] DEFAULT '{}'",
                "ADD COLUMN IF NOT EXISTS keywords text[] DEFAULT '{}'",
                "ADD COLUMN IF NOT EXISTS search_text text",
                "ADD COLUMN IF NOT EXISTS last_updated timestamp with time zone DEFAULT NOW()"
            ]
            
            # Execute each alteration in separate transaction
            for alter_sql in alterations:
                try:
                    cur.execute(f"ALTER TABLE experts_expert {alter_sql}")
                    logger.info(f"Column alteration completed: {alter_sql}")
                except Exception as e:
                    logger.warning(f"Column alteration warning: {alter_sql}: {e}")
                    continue

            # Create search text update function
            try:
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
            except Exception as e:
                logger.warning(f"Search text function creation warning: {e}")

            # Create trigger
            try:
                cur.execute("""
                    DROP TRIGGER IF EXISTS expert_search_text_trigger ON experts_expert;
                    CREATE TRIGGER expert_search_text_trigger
                    BEFORE INSERT OR UPDATE ON experts_expert
                    FOR EACH ROW
                    EXECUTE FUNCTION update_expert_search_text();
                """)
                logger.info("Created search text update trigger")
            except Exception as e:
                logger.warning(f"Trigger creation warning: {e}")

            # Create indexes
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_expert_domains ON experts_expert USING gin(normalized_domains)",
                "CREATE INDEX IF NOT EXISTS idx_expert_fields ON experts_expert USING gin(normalized_fields)",
                "CREATE INDEX IF NOT EXISTS idx_expert_skills ON experts_expert USING gin(normalized_skills)",
                "CREATE INDEX IF NOT EXISTS idx_expert_keywords ON experts_expert USING gin(keywords)",
                "CREATE INDEX IF NOT EXISTS idx_expert_search ON experts_expert USING gin(to_tsvector('english', COALESCE(search_text, '')))"
            ]
            
            for index_sql in indexes:
                try:
                    cur.execute(index_sql)
                    logger.info("Created index successfully")
                except Exception as e:
                    logger.warning(f"Index creation warning: {e}")
                    continue

            # Update existing rows
            try:
                cur.execute("UPDATE experts_expert SET last_updated = NOW();")
                logger.info("Updated existing rows to trigger search text generation")
            except Exception as e:
                logger.warning(f"Row update warning: {e}")

            logger.info("Fixed experts_expert table structure and handled all columns and indexes")
            return True
        else:
            logger.warning("experts_expert table does not exist. It will be created when needed.")
            return True
            
    except Exception as e:
        logger.error(f"Error fixing experts_expert table: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def create_tables():
    conn = get_db_connection()
    conn.autocommit = True  # Switch to autocommit mode
    cur = conn.cursor()
    try:
        # Create extension in separate transaction
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            logger.info("UUID extension creation/verification completed")
        except Exception as e:
            logger.warning(f"UUID extension warning: {e}")

        # Define all table creation statements
        table_statements = [
            """
            CREATE TABLE IF NOT EXISTS experts_expert (
                id SERIAL PRIMARY KEY,
                firstname VARCHAR(255) NOT NULL,
                lastname VARCHAR(255) NOT NULL,
                designation VARCHAR(255),
                theme VARCHAR(255),
                unit VARCHAR(255),
                contact_details VARCHAR(255),
                knowledge_expertise JSONB,
                orcid VARCHAR(255),
                domains TEXT[],
                fields TEXT[],
                subfields TEXT[],
                password VARCHAR(255),
                is_superuser BOOLEAN DEFAULT FALSE,
                is_staff BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                last_login TIMESTAMP WITH TIME ZONE,
                date_joined TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                bio TEXT,
                email VARCHAR(200),
                middle_name VARCHAR(200)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS resources_resource (
                id SERIAL PRIMARY KEY,
                doi VARCHAR(255),
                title TEXT NOT NULL,
                abstract TEXT,
                summary TEXT,
                authors TEXT[],
                description TEXT,
                expert_id INTEGER,
                type VARCHAR(100),
                subtitles JSONB,
                publishers JSONB,
                collection VARCHAR(255),
                date_issue VARCHAR(255),
                citation VARCHAR(255),
                language VARCHAR(255),
                identifiers JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS auth_group (
                id SERIAL PRIMARY KEY,
                name VARCHAR(150)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS auth_permission (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                content_type_id INTEGER,
                codename VARCHAR(100)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS author_publication_ai (
                author_id INTEGER,
                doi VARCHAR(255)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS authors_ai (
                author_id SERIAL PRIMARY KEY,
                name TEXT,
                orcid VARCHAR(255),
                author_identifier VARCHAR(255)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_chatbox (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                expert_from_id INTEGER,
                expert_to_id INTEGER,
                name VARCHAR(200)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_chatboxmessage (
                id SERIAL PRIMARY KEY,
                message TEXT,
                read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                expert_from_id INTEGER,
                expert_to_id INTEGER,
                chatbox_id INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS expertise_categories (
                id SERIAL PRIMARY KEY,
                expert_orcid TEXT,
                original_term TEXT,
                domain TEXT,
                field TEXT,
                subfield TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS publications_ai (
                doi VARCHAR(255) PRIMARY KEY,
                title TEXT,
                abstract TEXT,
                summary TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS roles_role (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                description VARCHAR(255),
                active BOOLEAN DEFAULT TRUE,
                permissions JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                default_expert_role BOOLEAN DEFAULT FALSE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tags (
                tag_id SERIAL PRIMARY KEY,
                tag_name VARCHAR(255)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS query_history_ai (
                query_id SERIAL PRIMARY KEY,
                query TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                result_count INTEGER,
                search_type VARCHAR(50),
                user_id TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS term_frequencies (
                term VARCHAR(255) PRIMARY KEY,
                frequency INTEGER DEFAULT 1,
                expert_id INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS search_logs (
                id SERIAL PRIMARY KEY,
                query TEXT NOT NULL,
                user_id VARCHAR(255),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                response_time INTERVAL,
                result_count INTEGER,
                clicked BOOLEAN DEFAULT FALSE,
                search_type VARCHAR(50),
                success_rate FLOAT,
                page_number INTEGER DEFAULT 1,
                filters JSONB
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS expert_searches (
                id SERIAL PRIMARY KEY,
                search_id INTEGER REFERENCES search_logs(id),
                expert_id VARCHAR(255),
                rank_position INTEGER,
                clicked BOOLEAN DEFAULT FALSE,
                click_timestamp TIMESTAMP,
                session_duration INTERVAL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS query_predictions (
                id SERIAL PRIMARY KEY,
                partial_query TEXT NOT NULL,
                predicted_query TEXT NOT NULL,
                selected BOOLEAN DEFAULT FALSE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confidence_score FLOAT,
                user_id VARCHAR(255)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS search_sessions (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255),
                start_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_timestamp TIMESTAMP,
                query_count INTEGER DEFAULT 1,
                successful_searches INTEGER DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS search_performance (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                avg_response_time INTERVAL,
                cache_hit_rate FLOAT,
                error_rate FLOAT,
                total_queries INTEGER,
                unique_users INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) UNIQUE NOT NULL,
                user_id VARCHAR(255) NOT NULL,
                start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP WITH TIME ZONE,
                total_messages INTEGER DEFAULT 0,
                successful BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_interactions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) REFERENCES chat_sessions(session_id),
                user_id VARCHAR(255) NOT NULL,
                query TEXT NOT NULL,
                response TEXT,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                response_time FLOAT,
                intent_type VARCHAR(255),
                intent_confidence FLOAT,
                expert_matches INTEGER,
                error_occurred BOOLEAN DEFAULT FALSE,
                context JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_analytics (
                id SERIAL PRIMARY KEY,
                interaction_id INTEGER REFERENCES chat_interactions(id),
                expert_id VARCHAR(255),
                similarity_score FLOAT,
                rank_position INTEGER,
                clicked BOOLEAN DEFAULT FALSE,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS expert_matching_logs (
                id SERIAL PRIMARY KEY,
                expert_id VARCHAR(255) NOT NULL,
                matched_expert_id VARCHAR(255) NOT NULL,
                similarity_score FLOAT,
                shared_domains JSONB,
                shared_fields INTEGER,
                shared_skills INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                successful BOOLEAN DEFAULT TRUE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS domain_expertise_analytics (
                id SERIAL PRIMARY KEY,
                domain_name VARCHAR(255) NOT NULL UNIQUE,
                field_name VARCHAR(255),
                subfield_name VARCHAR(255),
                expert_count INTEGER DEFAULT 0,
                match_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS expert_processing_logs (
                id SERIAL PRIMARY KEY,
                expert_id VARCHAR(255),
                processing_time FLOAT,
                domains_count INTEGER,
                fields_count INTEGER,
                success BOOLEAN,
                error_message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS expert_summary_logs (
                id SERIAL PRIMARY KEY,
                expert_id VARCHAR(255),
                total_domains INTEGER,
                total_fields INTEGER,
                total_subfields INTEGER,
                expertise_depth INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS collaboration_history (
                id SERIAL PRIMARY KEY,
                expert_id VARCHAR(255) NOT NULL,
                collaborator_id VARCHAR(255) NOT NULL,
                collaboration_score FLOAT NOT NULL,
                shared_domains JSONB,
                result_type VARCHAR(50),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]

        # Create each table in a separate transaction
        for table_sql in table_statements:
            try:
                cur.execute(table_sql)
                logger.info("Table creation/verification completed successfully")
            except Exception as e:
                logger.warning(f"Table creation warning: {e}")
                continue

        # Add type check and correction for shared_domains
        try:
            # Check if the column exists and get its type
            cur.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'expert_matching_logs' 
                AND column_name = 'shared_domains';
            """)
            current_type = cur.fetchone()
            
            if current_type and current_type[0].lower() == 'integer':
                # Drop dependent view first
                cur.execute("DROP VIEW IF EXISTS expert_matching_metrics CASCADE;")
                
                # Alter the column type
                cur.execute("""
                    ALTER TABLE expert_matching_logs 
                    ALTER COLUMN shared_domains TYPE JSONB 
                    USING CASE 
                        WHEN shared_domains IS NULL THEN '[]'::jsonb
                        ELSE jsonb_build_array(shared_domains::text)
                    END;
                """)
                logger.info("Successfully altered shared_domains column to JSONB type")
        except Exception as e:
            logger.warning(f"Column alteration warning for expert_matching_logs.shared_domains: {e}")

        # Add unique constraint to domain_expertise_analytics if it doesn't exist
        try:
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'domain_expertise_analytics_domain_name_key'
                    ) THEN
                        ALTER TABLE domain_expertise_analytics
                        ADD CONSTRAINT domain_expertise_analytics_domain_name_key
                        UNIQUE (domain_name);
                    END IF;
                END $$;
            """)
            logger.info("Successfully added unique constraint to domain_expertise_analytics.domain_name")
        except Exception as e:
            logger.warning(f"Constraint addition warning for domain_expertise_analytics: {e}")

        # Define all index creation statements
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_experts_name ON experts_expert (firstname, lastname)",
            "CREATE INDEX IF NOT EXISTS idx_query_history_timestamp ON query_history_ai (timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_query_history_user ON query_history_ai (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_updated ON chat_chatbox (updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_chat_message_created ON chat_chatboxmessage (created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_expertise_orcid ON expertise_categories (expert_orcid)",
            "CREATE INDEX IF NOT EXISTS idx_publications_title ON publications_ai USING gin(to_tsvector('english', title))",
            "CREATE INDEX IF NOT EXISTS idx_search_logs_timestamp ON search_logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_search_logs_user_id ON search_logs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_search_logs_query ON search_logs(query)",
            "CREATE INDEX IF NOT EXISTS idx_expert_searches_expert_id ON expert_searches(expert_id)",
            "CREATE INDEX IF NOT EXISTS idx_query_predictions_partial ON query_predictions(partial_query)",
            "CREATE INDEX IF NOT EXISTS idx_search_sessions_user_id ON search_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_sessions_timestamp ON chat_sessions(start_time)",
            "CREATE INDEX IF NOT EXISTS idx_chat_interactions_session ON chat_interactions(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_interactions_timestamp ON chat_interactions(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_chat_analytics_interaction ON chat_analytics(interaction_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_analytics_expert ON chat_analytics(expert_id)",
            "CREATE INDEX IF NOT EXISTS idx_matching_expert_id ON expert_matching_logs(expert_id)",
            "CREATE INDEX IF NOT EXISTS idx_matching_matched_expert ON expert_matching_logs(matched_expert_id)",
            "CREATE INDEX IF NOT EXISTS idx_domain_expertise_name ON domain_expertise_analytics(domain_name)",
            "CREATE INDEX IF NOT EXISTS idx_collab_experts ON collaboration_history(expert_id, collaborator_id)",
            "CREATE INDEX IF NOT EXISTS idx_domain_expertise_name_match ON domain_expertise_analytics(domain_name, match_count)"
        ]

        # Create each index in a separate transaction
        for index_sql in index_statements:
            try:
                cur.execute(index_sql)
                logger.info("Index creation/verification completed successfully")
            except Exception as e:
                logger.warning(f"Index creation warning: {e}")
                continue

        # Create views in separate transactions
        view_statements = [
            """
            CREATE OR REPLACE VIEW daily_search_metrics AS
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as total_searches,
                COUNT(DISTINCT user_id) as unique_users,
                AVG(EXTRACT(EPOCH FROM response_time)) as avg_response_time_seconds,
                SUM(CASE WHEN clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as click_through_rate
            FROM search_logs
            GROUP BY DATE(timestamp)
            """,
            """
            CREATE OR REPLACE VIEW expert_search_metrics AS
            SELECT 
                es.expert_id,
                COUNT(*) as total_appearances,
                AVG(es.rank_position) as avg_rank,
                SUM(CASE WHEN es.clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as click_through_rate
            FROM expert_searches es
            GROUP BY es.expert_id
            """,
            """
            CREATE OR REPLACE VIEW chat_daily_metrics AS
            SELECT 
                DATE(timestamp) as date,
                COUNT(DISTINCT session_id) as total_sessions,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(*) as total_interactions,
                AVG(response_time) as avg_response_time,
                SUM(CASE WHEN error_occurred THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as error_rate
            FROM chat_interactions
            GROUP BY DATE(timestamp)
            """,
            """
            CREATE OR REPLACE VIEW chat_expert_matching_metrics AS
            SELECT 
                ca.expert_id,
                COUNT(*) as total_matches,
                AVG(ca.similarity_score) as avg_similarity,
                AVG(ca.rank_position) as avg_rank,
                SUM(CASE WHEN ca.clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as click_through_rate
            FROM chat_analytics ca
            GROUP BY ca.expert_id
            """,
            """
            CREATE OR REPLACE VIEW expert_matching_metrics AS
            SELECT 
                expert_id,
                COUNT(*) as total_matches,
                AVG(similarity_score) as avg_similarity,
                AVG(CAST(jsonb_array_length(shared_domains) AS FLOAT)) as avg_shared_domains,
                COUNT(DISTINCT matched_expert_id) as unique_matches,
                SUM(CASE WHEN successful THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as success_rate
            FROM expert_matching_logs
            GROUP BY expert_id
            """,
            """
            CREATE OR REPLACE VIEW domain_matching_metrics AS
            SELECT 
                d.domain_name,
                d.expert_count,
                d.match_count,
                d.match_count::FLOAT / NULLIF(d.expert_count, 0) as match_rate,
                COUNT(DISTINCT em.expert_id) as active_experts
            FROM domain_expertise_analytics d
            LEFT JOIN expert_matching_logs em 
                ON em.timestamp >= NOW() - interval '30 days'
            GROUP BY d.domain_name, d.expert_count, d.match_count
            """
        ]

        # Create each view in a separate transaction
        for view_sql in view_statements:
            try:
                cur.execute(view_sql)
                logger.info("View creation/verification completed successfully")
            except Exception as e:
                logger.warning(f"View creation warning: {e}")
                continue

        # Create trigger function
        trigger_function = """
            CREATE OR REPLACE FUNCTION update_domain_match_count()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.shared_domains IS NOT NULL THEN
                    IF jsonb_typeof(NEW.shared_domains) = 'array' THEN
                        UPDATE domain_expertise_analytics
                        SET match_count = match_count + 1,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE domain_name IN (
                            SELECT value::text
                            FROM jsonb_array_elements_text(NEW.shared_domains)
                        );
                    ELSE
                        UPDATE domain_expertise_analytics
                        SET match_count = match_count + 1,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE domain_name = NEW.shared_domains::text;
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """

        # Create trigger function in separate transaction
        try:
            cur.execute(trigger_function)
            logger.info("Trigger function creation completed successfully")
        except Exception as e:
            logger.warning(f"Trigger function creation warning: {e}")

        # Create trigger
        try:
            cur.execute("DROP TRIGGER IF EXISTS trigger_update_domain_matches ON expert_matching_logs;")
            cur.execute("""
                CREATE TRIGGER trigger_update_domain_matches
                    AFTER INSERT ON expert_matching_logs
                    FOR EACH ROW
                    EXECUTE FUNCTION update_domain_match_count();
            """)
            logger.info("Trigger creation completed successfully")
        except Exception as e:
            logger.warning(f"Trigger creation warning: {e}")

        logger.info("All database objects created/verified successfully")
        return True

    except Exception as e:
        logger.error(f"Error in database initialization: {e}")
        return False
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
                    firstname, lastname, designation, theme, unit, contact_details, knowledge_expertise
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
            """, (
                firstname, lastname, designation, theme, unit, contact_details,
                json.dumps(expertise_list) if expertise_list else None
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
