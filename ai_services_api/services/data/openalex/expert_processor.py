import logging
import aiohttp
import pandas as pd
import requests
from typing import List, Tuple, Dict, Optional
import asyncio
from ai_services_api.services.data.openalex.database_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ExpertProcessor:
    def __init__(self, db: DatabaseManager, base_url: str):
        """Initialize ExpertProcessor."""
        self.db = db
        self.base_url = base_url
        self.session = None

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

    async def get_expert_domains(self, session: aiohttp.ClientSession, 
                               firstname: str, lastname: str, openalex_id: str) -> Tuple[List, List, List]:
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

    def close(self):
        """Close database connection."""
        if hasattr(self, 'db'):
            self.db.close()