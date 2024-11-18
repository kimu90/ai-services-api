import requests
from typing import List
from config.settings import settings
from core.models import Publication
import logging

logger = logging.getLogger(__name__)

class OpenAlexService:
    def __init__(self):
        self.base_url = settings.OPENALEX_API_URL
        
    async def fetch_publications(self) -> List[Publication]:
        """Fetch APHRC publications from OpenAlex using institution ID"""
        try:
            # Using the correct institution ID to filter publications
            params = {
                'filter': 'institutions.id:I4210129448',
                'per_page': 100
            }
            
            publications = []
            page = 1
            
            while True:
                params['page'] = page
                response = requests.get(f"{self.base_url}/works", params=params)
                response.raise_for_status()
                
                data = response.json()
                if not data['results']:
                    break
                    
                for item in data['results']:
                    pub = Publication(
                        title=item['title'],
                        abstract=item.get('abstract'),
                        doi=item.get('doi'),
                        source_system='openalex'
                    )
                    publications.append(pub)
                    
                page += 1
                
            return publications
            
        except Exception as e:
            logger.error(f"Error fetching OpenAlex publications: {str(e)}")
            raise
