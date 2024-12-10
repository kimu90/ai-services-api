import os
import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dotenv import load_dotenv
import pandas as pd
import psycopg2
from urllib.parse import urlparse
import json

from ai_services_api.services.data.openalex.database_manager import DatabaseManager
from ai_services_api.services.data.openalex.publication_processor import PublicationProcessor
from ai_services_api.services.data.openalex.ai_summarizer import TextSummarizer
import requests
from ai_services_api.services.data.openalex.expert_processor import ExpertProcessor


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

class OpenAlexProcessor:
    def __init__(self):
        """Initialize the OpenAlex processor with necessary components."""
        try:
            # Load environment variables
            load_dotenv()
            
            # Set up base configuration
            self.base_url = os.getenv('OPENALEX_API_URL', 'https://api.openalex.org')
            self.session = None
            
            # Initialize components
            self.db = DatabaseManager()
            self.expert_processor = ExpertProcessor(self.db, self.base_url)
            logger.info("OpenAlexProcessor initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing OpenAlexProcessor: {e}")
            raise
            
    async def load_initial_experts(self, expertise_csv: str):
        """Load initial expert data from expertise CSV."""
        def prepare_array_or_jsonb(data, is_jsonb=False):
            if isinstance(data, list):
                return json.dumps(data) if is_jsonb else data
            elif data:
                return json.dumps([data]) if is_jsonb else [data]
            else:
                return '[]' if is_jsonb else []

        try:
            if not os.path.exists(expertise_csv):
                raise FileNotFoundError(f"Expertise CSV file not found: {expertise_csv}")

            logger.info(f"Loading initial expert data from {expertise_csv}")
            
            conn = get_db_connection()
            cur = conn.cursor()

            # Check column types
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'experts_expert' 
                AND column_name IN ('knowledge_expertise', 'domains', 'fields', 'subfields');
            """)
            column_types = dict(cur.fetchall())

            df = pd.read_csv(expertise_csv)
            for _, row in df.iterrows():
                try:
                    firstname = row['Firstname']
                    lastname = row['Lastname']
                    designation = row['Designation']
                    theme = row['Theme']
                    unit = row['Unit']
                    contact_details = row['Contact Details']
                    expertise_str = row['Knowledge and Expertise']
                    
                    if pd.isna(expertise_str):
                        expertise_list = []
                    else:
                        expertise_list = [exp.strip() for exp in expertise_str.split(',') if exp.strip()]

                    cur.execute("""
                        INSERT INTO experts_expert (
                            firstname, lastname, designation, theme, unit, contact_details, 
                            knowledge_expertise, domains, fields, subfields
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) ON CONFLICT (firstname, lastname) DO UPDATE
                        SET designation = %s,
                            theme = %s,
                            unit = %s,
                            contact_details = %s,
                            knowledge_expertise = 
                                COALESCE(experts_expert.knowledge_expertise, %s) || %s,
                            domains = 
                                COALESCE(experts_expert.domains, %s),
                            fields = 
                                COALESCE(experts_expert.fields, %s),
                            subfields = 
                                COALESCE(experts_expert.subfields, %s)
                        RETURNING id
                    """, (
                        firstname, lastname, designation, theme, unit, contact_details,
                        prepare_array_or_jsonb(expertise_list, column_types['knowledge_expertise'] == 'jsonb'),
                        prepare_array_or_jsonb([], column_types['domains'] == 'jsonb'),
                        prepare_array_or_jsonb([], column_types['fields'] == 'jsonb'),
                        prepare_array_or_jsonb([], column_types['subfields'] == 'jsonb'),
                        designation, theme, unit, contact_details,
                        '[]' if column_types['knowledge_expertise'] == 'jsonb' else [],
                        prepare_array_or_jsonb(expertise_list, column_types['knowledge_expertise'] == 'jsonb'),
                        '[]' if column_types['domains'] == 'jsonb' else [],
                        '[]' if column_types['fields'] == 'jsonb' else [],
                        '[]' if column_types['subfields'] == 'jsonb' else []
                    ))

                    conn.commit()
                    logger.info(f"Added/updated expert data for {firstname} {lastname}")

                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error processing row for {row.get('Firstname', 'Unknown')} {row.get('Lastname', 'Unknown')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error loading initial expert data: {e}")
            raise
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()

    async def _update_single_expert(self, session: aiohttp.ClientSession, 
                                  expert_id: int, firstname: str, lastname: str):
        """Update a single expert with OpenAlex data."""
        try:
            success = await self.expert_processor.update_expert_fields(
                session, firstname, lastname
            )
            if success:
                logger.info(f"Updated data for {firstname} {lastname}")
            else:
                logger.warning(f"Could not update fields for {firstname} {lastname}")
        except Exception as e:
            logger.error(f"Error processing expert {firstname} {lastname}: {e}")

    async def update_experts_with_openalex(self):
        """Update experts with OpenAlex data."""
        try:
            # Get all experts without ORCID
            experts = self.db.execute("""
                SELECT id, firstname, lastname
                FROM experts_expert
                WHERE orcid IS NULL OR orcid = ''
            """)
            
            if not experts:
                logger.info("No experts found requiring OpenAlex update")
                return
            
            logger.info(f"Found {len(experts)} experts to update")
            
            async with aiohttp.ClientSession() as session:
                # Process experts in batches to avoid overloading
                batch_size = 5
                for i in range(0, len(experts), batch_size):
                    batch = experts[i:i + batch_size]
                    tasks = []
                    
                    for expert_id, firstname, lastname in batch:
                        task = asyncio.create_task(
                            self._update_single_expert(session, expert_id, firstname, lastname)
                        )
                        tasks.append(task)
                    
                    # Wait for batch to complete
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Add delay between batches
                    if i + batch_size < len(experts):
                        await asyncio.sleep(2)

            logger.info("Expert update process completed")
                        
        except Exception as e:
            logger.error(f"Error updating experts with OpenAlex data: {e}")
            raise

    
    async def update_expert_fields(self, session: aiohttp.ClientSession, 
                                  firstname: str, lastname: str) -> bool:
        """Update expert fields with OpenAlex data."""
        try:
            # Get OpenAlex IDs
            orcid, openalex_id = self.get_expert_openalex_data(firstname, lastname)
            
            if openalex_id:
                # Get domains, fields, and subfields
                domains, fields, subfields = await self.get_expert_domains(
                    session, firstname, lastname, openalex_id
                )
                
                # Update database
                self.db.execute("""
                    UPDATE experts_expert
                    SET orcid = COALESCE(NULLIF(%s, ''), orcid),
                        domains = ARRAY(
                            SELECT DISTINCT unnest(
                                COALESCE(experts_expert.domains, '{}') || %s::text[]
                            )
                        ),
                        fields = ARRAY(
                            SELECT DISTINCT unnest(
                                COALESCE(experts_expert.fields, '{}') || %s::text[]
                            )
                        ),
                        subfields = ARRAY(
                            SELECT DISTINCT unnest(
                                COALESCE(experts_expert.subfields, '{}') || %s::text[]
                            )
                        )
                    WHERE firstname = %s AND lastname = %s
                    RETURNING id
                """, (
                    orcid,
                    domains,
                    fields,
                    subfields,
                    firstname,
                    lastname
                ))
                
                logger.info(f"Updated OpenAlex data for {firstname} {lastname}")
                return True
            else:
                logger.warning(f"No OpenAlex ID found for {firstname} {lastname}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating expert fields for {firstname} {lastname}: {e}")
            return False

    async def get_expert_domains(self, session: aiohttp.ClientSession, 
                               firstname: str, lastname: str, openalex_id: str) -> Tuple[List[str], List[str], List[str]]:
        """Get expert domains from their works."""
        works = await self.get_expert_works(session, openalex_id)
        
        domains = set()
        fields = set()
        subfields = set()

        logger.info(f"Processing {len(works)} works for {firstname} {lastname}")

        for work in works:
            try:
                topics = work.get('topics', [])
                if not topics:
                    continue

                for topic in topics:
                    domain = topic.get('domain', {}).get('display_name')
                    field = topic.get('field', {}).get('display_name')
                    topic_subfields = [sf.get('display_name') for sf in topic.get('subfields', [])]

                    if domain:
                        domains.add(domain)
                    if field:
                        fields.add(field)
                    subfields.update(sf for sf in topic_subfields if sf)
            except Exception as e:
                logger.error(f"Error processing work topic: {e}")
                continue

        return list(domains), list(fields), list(subfields)

    async def get_expert_works(self, session: aiohttp.ClientSession, openalex_id: str, 
                             retries: int = 3, delay: int = 5) -> List[Dict]:
        """Fetch expert works from OpenAlex."""
        works_url = f"{self.base_url}/works"
        params = {
            'filter': f"authorships.author.id:{openalex_id}",
            'per-page': 50
        }

        logger.info(f"Fetching works for OpenAlex_ID: {openalex_id}")
        
        for attempt in range(retries):
            try:
                async with session.get(works_url, params=params) as response:
                    if response.status == 200:
                        works_data = await response.json()
                        return works_data.get('results', [])
                    
                    elif response.status == 429:  # Rate limit
                        wait_time = delay * (attempt + 1)
                        logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Error fetching works: {response.status}")
                        break

            except Exception as e:
                logger.error(f"Error fetching works for {openalex_id}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                
        return []

    def get_expert_openalex_data(self, firstname: str, lastname: str) -> Tuple[str, str]:
        """Get expert's ORCID and OpenAlex ID."""
        search_url = f"{self.base_url}/authors"
        params = {
            "search": f"{firstname} {lastname}",
            "filter": "display_name.search:" + f'"{firstname} {lastname}"'
        }
        
        try:
            for attempt in range(3):  # Add retry logic
                try:
                    response = requests.get(search_url, params=params)
                    response.raise_for_status()
                    
                    if response.status_code == 200:
                        results = response.json().get('results', [])
                        if results:
                            author = results[0]
                            orcid = author.get('orcid', '')
                            openalex_id = author.get('id', '')
                            return orcid, openalex_id
                    
                    elif response.status_code == 429:  # Rate limit
                        wait_time = (attempt + 1) * 5
                        logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                        asyncio.sleep(wait_time)
                        continue
                        
                except requests.RequestException as e:
                    logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                    if attempt < 2:  # Only sleep if we're going to retry
                        asyncio.sleep(5)
                    continue
                
        except Exception as e:
            logger.error(f"Error fetching data for {firstname} {lastname}: {e}")
        return '', ''

    async def process_publications(self, pub_processor: PublicationProcessor):
        try:
            # Get all experts with ORCID, excluding those with "Unknown" first or last name
            experts = self.db.execute("""
                SELECT id, firstname, lastname, orcid
                FROM experts_expert
                WHERE orcid IS NOT NULL AND orcid != '' AND firstname <> 'Unknown' AND lastname <> 'Unknown'
            """)
            
            if not experts:
                logger.info("No experts found with ORCID for publication processing")
                return
            
            publication_count = 0
            max_publications = 25
            
            logger.info(f"Processing publications for {len(experts)} experts")

            async with aiohttp.ClientSession() as session:
                for expert_id, firstname, lastname, orcid in experts:
                    try:
                        if publication_count >= max_publications:
                            logger.info("Reached maximum publication limit")
                            break

                        logger.info(f"Fetching publications for {firstname} {lastname}")
                        publications = await self._fetch_expert_publications(session, orcid)
                        
                        for work in publications:
                            try:
                                if pub_processor.process_single_work(work):
                                    publication_count += 1
                                    logger.info(
                                        f"Processed publication {publication_count}/{max_publications}: "
                                        f"{work.get('title', 'Unknown Title')}"
                                    )
                                
                                if publication_count >= max_publications:
                                    break
                                    
                            except Exception as e:
                                logger.error(f"Error processing work: {e}")
                                continue
                                
                    except Exception as e:
                        logger.error(f"Error processing publications for {firstname} {lastname}: {e}")
                        continue
                        
            logger.info(f"Publications processing completed. Total processed: {publication_count}")
            
        except Exception as e:
            logger.error(f"Error in publications processing: {e}")
            raise

    async def _fetch_expert_publications(self, session: aiohttp.ClientSession, orcid: str,
                                       per_page: int = 5) -> List[Dict[str, Any]]:
        """Fetch publications for an expert from OpenAlex."""
        try:
            url = f"{self.base_url}/works"
            params = {
                'filter': f"author.orcid:{orcid}",
                'per_page': per_page
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('results', [])
                elif response.status == 429:  # Rate limit
                    logger.warning("Rate limit hit, waiting before retry...")
                    await asyncio.sleep(5)
                    return []
                else:
                    logger.error(f"Failed to fetch publications: Status {response.status}")
                    return []
                
        except Exception as e:
            logger.error(f"Error fetching publications: {e}")
            return []

    async def _validate_expert(self, expert_id: int, firstname: str, lastname: str) -> bool:
        """Validate expert data."""
        try:
            if not all([expert_id, firstname, lastname]):
                logger.warning(f"Invalid expert data: id={expert_id}, name={firstname} {lastname}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating expert data: {e}")
            return False

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        try:
            if hasattr(self, 'db'):
                self.db.close()
            logger.info("OpenAlexProcessor resources cleaned up")
        except Exception as e:
            logger.error(f"Error closing resources: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close()