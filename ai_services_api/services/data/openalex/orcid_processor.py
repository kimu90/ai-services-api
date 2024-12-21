import os
import logging
import asyncio
import aiohttp
import requests
from typing import List, Dict, Optional

from ai_services_api.services.data.openalex.database_manager import DatabaseManager
from ai_services_api.services.data.openalex.ai_summarizer import TextSummarizer
from ai_services_api.services.data.openalex.publication_processor import PublicationProcessor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class OrcidProcessor:
    def __init__(self, db: DatabaseManager = None, summarizer: TextSummarizer = None):
        """
        Initialize ORCID Processor with database and summarizer.
        
        Args:
            db (DatabaseManager, optional): Database manager instance
            summarizer (TextSummarizer, optional): Summarizer instance
        """
        self.db = db or DatabaseManager()
        self.summarizer = summarizer or TextSummarizer()
        self.base_url = "https://pub.orcid.org/v3.0"
        
        # Get ORCID API credentials
        self.client_id = os.getenv('ORCID_CLIENT_ID')
        self.client_secret = os.getenv('ORCID_CLIENT_SECRET')
        
        if not self.client_id or not self.client_secret:
            raise ValueError("ORCID API credentials not found")
        
        # Get access token
        self.access_token = self._get_access_token()

    def _get_access_token(self) -> str:
        """
        Retrieve access token for ORCID API.
        
        Returns:
            str: Access token for API requests
        """
        token_url = "https://orcid.org/oauth/token"
        response = requests.post(
            token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
                "scope": "/read-public"
            },
            headers={"Accept": "application/json"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get ORCID access token: {response.text}")
        
        return response.json()["access_token"]

    def _get_experts_with_orcid(self) -> List[Dict]:
        """
        Retrieve experts with ORCID identifiers from the database.
        
        Returns:
            List[Dict]: List of experts with ORCID
        """
        try:
            experts = self.db.execute("""
                SELECT id, first_name, last_name, orcid
                FROM experts_expert
                WHERE orcid IS NOT NULL 
                  AND orcid != '' 
                  AND orcid != 'Unknown'
                  AND first_name != 'Unknown' 
                  AND last_name != 'Unknown'
            """)
            
            return [
                {
                    'id': expert[0],
                    'first_name': expert[1],
                    'last_name': expert[2],
                    'orcid': expert[3]
                } for expert in experts
            ]
        except Exception as e:
            logger.error(f"Error retrieving experts with ORCID: {e}")
            return []

    async def process_publications(self, pub_processor: PublicationProcessor, source: str = 'orcid') -> None:
        """
        Process publications for experts with ORCID.
        
        Args:
            pub_processor (PublicationProcessor): Publication processor instance
            source (str, optional): Source of publications. Defaults to 'orcid'.
        """
        # Get experts with ORCID
        experts = self._get_experts_with_orcid()
        
        if not experts:
            logger.info("No experts with ORCID found")
            return
        
        logger.info(f"Processing publications for {len(experts)} experts")
        
        # Process publications for each expert
        publication_count = 0
        max_publications = 10  # Changed to 10 total publications
        
        async with aiohttp.ClientSession() as session:
            for expert in experts:
                try:
                    if publication_count >= max_publications:
                        logger.info("Reached maximum total publication limit")
                        break
                    
                    # Fetch publications for this expert
                    publications = await self._fetch_expert_publications(
                        session, 
                        expert['orcid']
                    )
                    
                    for work in publications:
                        try:
                            # Process publication with ORCID source
                            if pub_processor.process_single_work(work, source=source):
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
                    logger.error(
                        f"Error processing publications for {expert['first_name']} {expert['last_name']}: {e}"
                    )
                    continue
        
        logger.info(f"ORCID publications processing completed. Total processed: {publication_count}")

    async def _fetch_expert_publications(
        self, 
        session: aiohttp.ClientSession, 
        orcid: str, 
        per_page: int = 5
    ) -> List[Dict]:
        """
        Fetch publications for an expert from ORCID.
        
        Args:
            session (aiohttp.ClientSession): Async HTTP session
            orcid (str): ORCID identifier
            per_page (int, optional): Number of publications to fetch. Defaults to 5.
        
        Returns:
            List[Dict]: List of publication works
        """
        try:
            # Prepare ORCID API request
            clean_orcid = orcid.replace('https://orcid.org/', '')
            url = f"{self.base_url}/{clean_orcid}/works"
            
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}"
            }
            
            params = {
                'per-page': per_page
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Convert ORCID works to a format compatible with publication processor
                    works = []
                    for group in data.get('group', []):
                        work_summaries = group.get('work-summary', [])
                        if not work_summaries:
                            continue
                        
                        # Take first work summary
                        summary = work_summaries[0]
                        
                        # Construct work dictionary
                        work = {
                            'title': summary.get('title', {}).get('title', {}).get('value', 'Unknown Title'),
                            'doi': self._get_identifier(summary, 'doi'),
                            'abstract_inverted_index': None,  # ORCID might not have this
                            'authorships': [],  # You might want to populate this
                            'concepts': []  # You might want to populate this
                        }
                        
                        works.append(work)
                    
                    return works
                
                elif response.status == 429:  # Rate limit
                    logger.warning("ORCID API rate limit hit")
                    return []
                else:
                    logger.error(f"Failed to fetch publications: Status {response.status}")
                    return []
        
        except Exception as e:
            logger.error(f"Error fetching ORCID publications: {e}")
            return []

    def _get_identifier(self, work_summary: Dict, id_type: str) -> str:
        """
        Extract a specific identifier from work summary.
        
        Args:
            work_summary (Dict): Work summary dictionary
            id_type (str): Type of identifier to extract (e.g., 'doi')
        
        Returns:
            str: Extracted identifier or empty string
        """
        try:
            external_ids = work_summary.get('external-ids', {}).get('external-id', [])
            for ext_id in external_ids:
                if ext_id.get('external-id-type') == id_type:
                    return ext_id.get('external-id-value', '')
        except Exception as e:
            logger.error(f"Error getting {id_type} identifier: {e}")
        return ''

    def close(self):
        """
        Close database connection and cleanup resources.
        """
        try:
            if hasattr(self, 'db'):
                self.db.close()
            logger.info("OrcidProcessor resources cleaned up")
        except Exception as e:
            logger.error(f"Error closing resources: {e}")
