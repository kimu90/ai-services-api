import httpx
from ai_services_api.services.recommendation.config import get_settings

settings = get_settings()

class OpenAlexService:
    def __init__(self):
        self.base_url = settings.OPENALEX_API_URL

    async def _fetch_data(self, endpoint: str, params: dict = None):
        """Helper method to fetch data from OpenAlex API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/{endpoint}", params=params, timeout=30)
                response.raise_for_status()  # Raises HTTPError for bad responses
                return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            print(f"Request error occurred: {e}")
        return None

    async def get_expert_data(self, orcid: str):
        """Fetch expert data from OpenAlex API."""
        data = await self._fetch_data('authors', params={'filter': f"orcid:{orcid}"})
        if data and 'results' in data:
            return data['results'][0] if data['results'] else None
        return None

    async def get_expert_domains(self, orcid: str):
        """Fetch expert's domains, fields, and subfields from their works using topics."""
        expert_data = await self.get_expert_data(orcid)
        if not expert_data:
            return []

        openalex_id = expert_data['id']
        domains_fields_subfields = []

        # Get the author's works
        works_data = await self._fetch_data('works', params={'filter': f"authorships.author.id:{openalex_id}", 'per-page': 50})
        if not works_data or 'results' not in works_data:
            return []

        # Extract unique domains, fields, and subfields from topics
        for work in works_data['results']:
            for topic in work.get('topics', []):  # Now using 'topics' instead of 'concepts'
                domain_name = topic.get('domain', {}).get('display_name', 'Unknown Domain')
                field_name = topic.get('field', {}).get('display_name', 'Unknown Field')
                subfield_name = topic.get('subfield', {}).get('display_name', 'Unknown Subfield')
                
                # Append each topic to the list
                domains_fields_subfields.append({
                    'domain': domain_name,
                    'field': field_name,
                    'subfield': subfield_name
                })

        # Remove duplicates based on domain, field, and subfield combination
        unique_items = {(item['domain'], item['field'], item['subfield']): item for item in domains_fields_subfields}
        return list(unique_items.values())

    async def get_expert_works(self, orcid: str):
        """Fetch expert's works."""
        expert_data = await self.get_expert_data(orcid)
        if not expert_data:
            return None

        openalex_id = expert_data['id']
        works_data = await self._fetch_data('works', params={'filter': f"authorships.author.id:{openalex_id}"})
        return works_data if works_data else None
