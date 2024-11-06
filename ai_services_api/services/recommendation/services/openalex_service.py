import httpx
from ai_services_api.services.recommendation.config import get_settings

settings = get_settings()

class OpenAlexService:
    def __init__(self):
        self.base_url = settings.OPENALEX_API_URL

    async def get_expert_data(self, orcid: str):
        """Fetch expert data from OpenAlex API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/authors", params={
                "filter": f"orcid:{orcid}"
            })
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    return results[0]
            return None

    async def get_expert_domains(self, orcid: str):
        """Fetch expert's domains from their works."""
        expert_data = await self.get_expert_data(orcid)
        if not expert_data:
            return []

        openalex_id = expert_data['id']
        domains = set()  # Use set to avoid duplicates

        async with httpx.AsyncClient() as client:
            # Get the author's works
            response = await client.get(f"{self.base_url}/works", params={
                "filter": f"author.id:{openalex_id}",
                "per-page": 50  # Adjust as needed
            })
            
            if response.status_code != 200:
                return []

            works = response.json().get('results', [])
            
            # Extract unique domains from concepts
            for work in works:
                concepts = work.get('concepts', [])
                for concept in concepts:
                    # Get the top-level domain from the concept
                    if 'level' in concept and concept['level'] == 0:  # Level 0 represents domains
                        domains.add((
                            concept['id'],
                            concept['display_name']
                        ))

        # Convert set to list of dictionaries
        return [{'id': d[0], 'display_name': d[1]} for d in domains]

    async def get_expert_works(self, orcid: str):
        """Fetch expert's works."""
        expert_data = await self.get_expert_data(orcid)
        if not expert_data:
            return None

        openalex_id = expert_data['id']
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/works", params={
                "filter": f"author.id:{openalex_id}"
            })
            if response.status_code == 200:
                return response.json()
            return None