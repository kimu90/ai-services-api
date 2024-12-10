import os
import psycopg2
from psycopg2 import sql
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from urllib.parse import urlparse
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

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
            'host': os.getenv('POSTGRES_HOST', '167.86.85.127'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'dbname': os.getenv('POSTGRES_DB', 'aphrc'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'p0stgres')
        }

def get_db_connection():
    """Create a connection to PostgreSQL database."""
    params = get_connection_params()
    try:
        conn = psycopg2.connect(**params)
        logger.info(f"Successfully connected to database: {params['dbname']}")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Error connecting to the database: {e}")
        raise

async def normalize_expertise(expertise_list: List[str]) -> Dict[str, List[str]]:
    """
    Use Gemini to normalize and categorize expertise
    """
    if not expertise_list:
        return {
            "domains": [],
            "fields": [],
            "skills": [],
            "keywords": []
        }

    prompt = f"""
    Analyze these expertise items: {', '.join(expertise_list)}
    Categorize them into:
    1. Broad domains (main research areas)
    2. Specific fields
    3. Technical skills
    4. Related keywords
    
    Return as a JSON structure with these exact keys:
    {{
        "domains": [],
        "fields": [],
        "skills": [],
        "keywords": []
    }}
    """

    try:
        response = model.generate_content(prompt)
        categories = eval(response.text)
        logger.info("Successfully normalized expertise using Gemini")
        return categories
    except Exception as e:
        logger.error(f"Error normalizing expertise: {e}")
        # Fallback categorization
        return {
            "domains": expertise_list[:2],
            "fields": expertise_list[2:4],
            "skills": expertise_list[4:],
            "keywords": expertise_list
        }

async def insert_expert(conn, expert_data: Dict[str, Any]):
    """Insert expert data into PostgreSQL database with enhanced expertise handling"""
    try:
        with conn.cursor() as cur:
            # Get expertise data
            expertise_list = expert_data.get('knowledge_expertise', [])
            
            # Normalize expertise using Gemini
            normalized_expertise = await normalize_expertise(expertise_list)
            
            # Extract or generate name components
            full_name = expert_data.get('display_name', '').split()
            firstname = full_name[0] if full_name else 'Unknown'
            lastname = ' '.join(full_name[1:]) if len(full_name) > 1 else 'Unknown'
            
            # Insert into experts table with normalized expertise
            cur.execute("""
                INSERT INTO experts_expert (
                    id,
                    firstname,
                    lastname,
                    knowledge_expertise,
                    domains,
                    fields,
                    subfields,
                    normalized_domains,
                    normalized_fields,
                    normalized_skills,
                    keywords,
                    last_updated
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    firstname = EXCLUDED.firstname,
                    lastname = EXCLUDED.lastname,
                    knowledge_expertise = EXCLUDED.knowledge_expertise,
                    domains = EXCLUDED.domains,
                    fields = EXCLUDED.fields,
                    subfields = EXCLUDED.subfields,
                    normalized_domains = EXCLUDED.normalized_domains,
                    normalized_fields = EXCLUDED.normalized_fields,
                    normalized_skills = EXCLUDED.normalized_skills,
                    keywords = EXCLUDED.keywords,
                    last_updated = NOW()
            """, (
                expert_data.get('id'),
                firstname,
                lastname,
                expertise_list,
                expert_data.get('domains', []),
                expert_data.get('fields', []),
                expert_data.get('subfields', []),
                normalized_expertise['domains'],
                normalized_expertise['fields'],
                normalized_expertise['skills'],
                normalized_expertise['keywords']
            ))
            
            conn.commit()
            logger.info(f"Successfully inserted/updated expert: {expert_data.get('id')}")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting expert data: {e}")
        raise

async def get_expert(conn, expert_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve expert data from PostgreSQL database with normalized expertise"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id,
                    firstname,
                    lastname,
                    knowledge_expertise,
                    domains,
                    fields,
                    subfields,
                    normalized_domains,
                    normalized_fields,
                    normalized_skills,
                    keywords,
                    last_updated
                FROM experts_expert
                WHERE id = %s
            """, (expert_id,))
            
            result = cur.fetchone()
            if result:
                return {
                    'id': result[0],
                    'firstname': result[1],
                    'lastname': result[2],
                    'knowledge_expertise': result[3],
                    'domains': result[4],
                    'fields': result[5],
                    'subfields': result[6],
                    'normalized_domains': result[7],
                    'normalized_fields': result[8],
                    'normalized_skills': result[9],
                    'keywords': result[10],
                    'last_updated': result[11]
                }
            return None
            
    except Exception as e:
        logger.error(f"Error retrieving expert data: {e}")
        return None

async def search_experts(conn, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search experts based on expertise, domains, fields, or keywords
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id,
                    firstname,
                    lastname,
                    knowledge_expertise,
                    normalized_domains,
                    normalized_fields,
                    normalized_skills
                FROM experts_expert
                WHERE 
                    to_tsvector('english', 
                        array_to_string(knowledge_expertise, ' ') || ' ' ||
                        array_to_string(normalized_domains, ' ') || ' ' ||
                        array_to_string(normalized_fields, ' ') || ' ' ||
                        array_to_string(normalized_skills, ' ')
                    ) @@ plainto_tsquery('english', %s)
                LIMIT %s
            """, (query, limit))
            
            results = cur.fetchall()
            experts = []
            for result in results:
                experts.append({
                    'id': result[0],
                    'firstname': result[1],
                    'lastname': result[2],
                    'knowledge_expertise': result[3],
                    'normalized_domains': result[4],
                    'normalized_fields': result[5],
                    'normalized_skills': result[6]
                })
            return experts
            
    except Exception as e:
        logger.error(f"Error searching experts: {e}")
        return []

async def update_expert_expertise(conn, expert_id: str, new_expertise: List[str]):
    """
    Update an expert's expertise and renormalize categories
    """
    try:
        # Normalize new expertise
        normalized = await normalize_expertise(new_expertise)
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE experts_expert
                SET 
                    knowledge_expertise = %s,
                    normalized_domains = %s,
                    normalized_fields = %s,
                    normalized_skills = %s,
                    keywords = %s,
                    last_updated = NOW()
                WHERE id = %s
            """, (
                new_expertise,
                normalized['domains'],
                normalized['fields'],
                normalized['skills'],
                normalized['keywords'],
                expert_id
            ))
            
            conn.commit()
            logger.info(f"Successfully updated expertise for expert: {expert_id}")
            return True
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating expert expertise: {e}")
        return False