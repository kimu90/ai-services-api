from typing import List
import asyncio
from sqlalchemy.orm import Session
from core.models import Publication
from core.database import get_db
from .website_service import WebsiteService
from .dspace_service import DSpaceService
from .orcid_service import OrcidService
from .openalex_service import OpenAlexService
import logging

logger = logging.getLogger(__name__)

class IntegrationService:
    def __init__(self):
        self.website_service = WebsiteService()
        self.dspace_service = DSpaceService()
        self.orcid_service = OrcidService()
        self.openalex_service = OpenAlexService()
        
    async def sync_all_data(self):
        """Synchronize data from all sources"""
        try:
            # Fetch data from all sources concurrently
            tasks = [
                self.website_service.fetch_publications(),
                self.dspace_service.fetch_publications(),
                self.orcid_service.fetch_publications(),
                self.openalex_service.fetch_publications()
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Merge all publications
            all_publications = []
            for pubs in results:
                all_publications.extend(pubs)
                
            # Deduplicate based on DOI
            unique_publications = {pub.doi: pub for pub in all_publications if pub.doi}
            
            # Save to database
            db = next(get_db())
            try:
                for pub in unique_publications.values():
                    existing_pub = db.query(Publication).filter_by(doi=pub.doi).first()
                    if existing_pub:
                        # Update existing publication
                        for key, value in pub.__dict__.items():
                            if key != 'id' and value is not None:
                                setattr(existing_pub, key, value)
                    else:
                        # Add new publication
                        db.add(pub)
                
                db.commit()
                logger.info(f"Successfully synchronized {len(unique_publications)} publications")
                
            except Exception as e:
                db.rollback()
                raise
                
        except Exception as e:
            logger.error(f"Error during data synchronization: {str(e)}")
            raise