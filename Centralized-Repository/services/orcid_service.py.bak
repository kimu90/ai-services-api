import requests
from typing import List
from config.settings import settings
from core.models import Publication
import logging

logger = logging.getLogger(__name__)

class OrcidService:
    def __init__(self):
        self.base_url = settings.ORCID_API_URL
        self.api_key = settings.ORCID_API_KEY
        
    async def fetch_publications(self) -> List[Publication]:
        """Fetch APHRC publications from ORCID and ensure DOI is included"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json'
            }
            
            # Get APHRC authors first
            response = requests.get(
                f"{self.base_url}/search",
                params={'q': 'affiliation-org-name:APHRC'},
                headers=headers
            )
            response.raise_for_status()
            
            publications = []
            for author in response.json()['result']:
                # Get publications for each author
                works_response = requests.get(
                    f"{self.base_url}/{author['orcid-identifier']['path']}/works",
                    headers=headers
                )
                works_response.raise_for_status()
                
                for work in works_response.json()['group']:
                    # Extract title
                    title = work['work-summary'][0]['title']['title']['value']
                    
                    # Attempt to get DOI
                    doi = None
                    external_ids = work.get('work-summary', [{}])[0].get('external-ids', {}).get('external-id', [])
                    for external_id in external_ids:
                        if external_id.get('external-id-type') == 'doi':
                            doi = external_id.get('external-id-value')
                            break
                    
                    # Ensure DOI is assigned correctly, even if it is None
                    pub = Publication(
                        title=title,
                        doi=doi if doi else None,  # Ensure DOI is set to None if not found
                        source_system='orcid'
                    )
                    publications.append(pub)
                    
            return publications
            
        except Exception as e:
            logger.error(f"Error fetching ORCID publications: {str(e)}")
            raise  # Re-raise the exception after logging it
