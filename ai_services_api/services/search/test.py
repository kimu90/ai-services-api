import os
import logging
import requests
from typing import Dict, List, Tuple, Optional, Any
import aiohttp
from dotenv import load_dotenv

# Import our custom modules
from ai_services_api.services.data.openalex.database_manager import DatabaseManager
from ai_services_api.services.data.openalex.expert_processor import ExpertProcessor
from ai_services_api.services.data.openalex.publication_processor import PublicationProcessor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class OpenAlexProcessor:
    def __init__(self):
        """Initialize the OpenAlex processor with necessary components."""
        # Load environment variables
        load_dotenv()
        
        # Set up base configuration
        self.base_url = os.getenv('OPENALEX_API_URL', 'https://api.openalex.org')
        
        # Initialize components
        self.db = DatabaseManager()
        self.expert_processor = ExpertProcessor(self.db, self.base_url)

    async def load_initial_experts(self, expertise_csv: str):
        """Load initial expert data from expertise.csv"""
        try:
            logger.info(f"Loading initial expert data from {expertise_csv}")
            await self.expert_processor.process_expertise_csv(expertise_csv)
            logger.info("Initial expert data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading initial expert data: {e}")
            raise

    async def update_experts_with_openalex(self):
        """Update experts with OpenAlex data."""
        try:
            # Get all experts without ORCID
            experts = self.db.execute("""
                SELECT id, firstname, lastname
                FROM research
                WHERE orcid IS NULL OR orcid = ''
            """)
            
            async with aiohttp.ClientSession() as session:
                for expert_id, firstname, lastname in experts:
                    try:
                        success = await self.expert_processor.update_expert_fields(
                            session, firstname, lastname
                        )
                        if not success:
                            logger.warning(f"Could not update fields for {firstname} {lastname} (ID: {expert_id})")
                    except Exception as e:
                        logger.error(f"Error processing expert {firstname} {lastname} (ID: {expert_id}): {e}")
                        continue
        except Exception as e:
            logger.error(f"Error updating experts with OpenAlex data: {e}")
            raise

    async def process_publications(self, pub_processor: PublicationProcessor):
        """Process publications for experts with ORCID."""
        try:
            # Get all experts with ORCID
            experts = self.db.execute("""
                SELECT id, firstname, lastname, orcid
                FROM research
                WHERE orcid IS NOT NULL AND orcid != ''
            """)
            
            async with aiohttp.ClientSession() as session:
                for expert_id, firstname, lastname, orcid in experts:
                    try:
                        logger.info(f"Fetching publications for {firstname} {lastname}")
                        
                        # Fetch works from OpenAlex
                        url = f"{self.base_url}/works?filter=author.orcid:{orcid}"
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                works = data.get('results', [])
                                
                                for work in works:
                                    try:
                                        if pub_processor.process_single_work(work):
                                            logger.info(f"Processed publication: {work.get('title', 'Unknown Title')}")
                                    except Exception as e:
                                        logger.error(f"Error processing work: {e}")
                                        continue
                            else:
                                logger.warning(f"Failed to fetch publications for {firstname} {lastname}")
                                
                    except Exception as e:
                        logger.error(f"Error processing publications for {firstname} {lastname}: {e}")
                        continue
                        
            logger.info("Publications processing completed")
            
        except Exception as e:
            logger.error(f"Error in publications processing: {e}")
            raise

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if hasattr(self, 'db'):
            self.db.close()