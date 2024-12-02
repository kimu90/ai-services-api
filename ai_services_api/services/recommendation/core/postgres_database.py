import os
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
import logging
from typing import Dict, Any, Optional

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
            'host': 'postgres' if in_docker else 'localhost',
            'port': '5432',
            'dbname': os.getenv('POSTGRES_DB', 'aphrcdb'),
            'user': os.getenv('POSTGRES_USER', 'aphrcuser'),
            'password': os.getenv('POSTGRES_PASSWORD', 'kimu')
        }

def get_db_connection(dbname=None):
    """Create a connection to PostgreSQL database."""
    params = get_connection_params()
    if dbname:
        params['dbname'] = dbname
        
    try:
        conn = psycopg2.connect(**params)
        logger.info(f"Successfully connected to database: {params['dbname']}")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Error connecting to the database: {e}")
        raise

def insert_expert(conn, expert_data: Dict[str, Any]):
    """Insert expert data into PostgreSQL database"""
    try:
        with conn.cursor() as cur:
            # Split name into first and last name
            full_name = expert_data.get('display_name', '').split()
            firstname = full_name[0] if full_name else 'Unknown'
            lastname = ' '.join(full_name[1:]) if len(full_name) > 1 else 'Unknown'
            
            # Extract domains, fields, and subfields arrays
            domains = [d['domain'] for d in expert_data.get('domains_fields_subfields', [])]
            fields = [f['field'] for f in expert_data.get('domains_fields_subfields', [])]
            subfields = [s['subfield'] for s in expert_data.get('domains_fields_subfields', [])]
            
            # Insert into experts table
            cur.execute("""
                INSERT INTO experts (orcid, firstname, lastname, domains, fields, subfields)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (orcid) 
                DO UPDATE SET 
                    firstname = EXCLUDED.firstname,
                    lastname = EXCLUDED.lastname,
                    domains = EXCLUDED.domains,
                    fields = EXCLUDED.fields,
                    subfields = EXCLUDED.subfields
            """, (
                expert_data['orcid'],
                firstname,
                lastname,
                domains,
                fields,
                subfields
            ))
            conn.commit()
            logger.info(f"Successfully inserted/updated expert: {expert_data['orcid']}")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting expert data: {e}")
        raise

def get_expert(conn, orcid: str) -> Optional[Dict[str, Any]]:
    """Retrieve expert data from PostgreSQL database"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT orcid, firstname, lastname, domains, fields, subfields
                FROM experts
                WHERE orcid = %s
            """, (orcid,))
            
            result = cur.fetchone()
            if result:
                return {
                    'orcid': result[0],
                    'firstname': result[1],
                    'lastname': result[2],
                    'domains': result[3],
                    'fields': result[4],
                    'subfields': result[5]
                }
            return None
            
    except Exception as e:
        logger.error(f"Error retrieving expert data: {e}")
        return None