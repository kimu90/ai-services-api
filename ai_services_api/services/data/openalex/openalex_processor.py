import os
import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

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
        try:
            if not os.path.exists(expertise_csv):
                raise FileNotFoundError(f"Expertise CSV file not found: {expertise_csv}")

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

    async def process_publications(self, pub_processor: PublicationProcessor):
        """Process publications for experts with ORCID."""
        try:
            # Get all experts with ORCID
            experts = self.db.execute("""
                SELECT id, firstname, lastname, orcid
                FROM experts_expert
                WHERE orcid IS NOT NULL AND orcid != ''
                LIMIT 5  -- Limit for testing, adjust as needed
            """)
            
            if not experts:
                logger.info("No experts found with ORCID for publication processing")
                return
            
            publication_count = 0
            max_publications = 25  # Total publication limit
            
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