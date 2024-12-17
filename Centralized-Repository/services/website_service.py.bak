import requests
from typing import List
from config.settings import settings
from core.models import Publication
import logging

logger = logging.getLogger(__name__)

class WebsiteService:
    def __init__(self):
        self.base_url = settings.WEBSITE_API_URL
        
    async def fetch_publications(self) -> List[Publication]:
        """Fetch publications from APHRC website"""
        try:
            response = requests.get(f"{self.base_url}/publications")
            response.raise_for_status()
            
            publications = []
            for item in response.json():
                pub = Publication(
                    title=item['title'],
                    abstract=item.get('abstract'),
                    doi=item.get('doi'),
                    source_system='website'
                )
                publications.append(pub)
                
            return publications
            
        except Exception as e:
            logger.error(f"Error fetching website publications: {str(e)}")
            raise

    async def download_document(self, doc_id: str) -> bytes:
        """Download document from website"""
        try:
            response = requests.get(f"{self.base_url}/downloads/{doc_id}")
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading document {doc_id}: {str(e)}")
            raise