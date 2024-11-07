import requests
import time
import httpx
from ai_services_api.services.recommendation.config import get_settings

BASE_WORKS_URL = 'https://api.openalex.org/works'
BATCH_SIZE = 10
INITIAL_DELAY = 5.0  # Delay in seconds between batches
MAX_BACKOFF_DELAY = 100.0  # Maximum backoff delay in seconds

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

class ExpertService:
    def __init__(self):
        self.graph = GraphDatabase()
        self.openalex = OpenAlexService()

    async def add_expert(self, orcid: str):
        """Add or update expert in the graph with domain, field, and subfield relationships."""
        # Step 1: Fetch OpenAlex ID using ORCID
        expert_data = await self.openalex.get_expert_data(orcid)
        if not expert_data:
            return None
        
        openalex_id = expert_data.get('id')

        # Step 2: Create expert node in the graph
        self.graph.create_expert_node(
            orcid=orcid,
            name=expert_data.get('display_name', '')
        )

        # Step 3: Fetch the works for the expert using the OpenAlex ID
        works = []
        page = 1
        delay = INITIAL_DELAY
        while True:
            requests_made = 0
            for _ in range(BATCH_SIZE):
                params = {'filter': f'authorships.author.id:{openalex_id}', 'per_page': 100, 'page': page}
                response = requests.get(BASE_WORKS_URL, params=params)

                if response.status_code == 200:
                    data = response.json()
                    works.extend(data['results'])
                    if len(data['results']) < 100:
                        break  # No more pages
                    page += 1
                    requests_made += 1
                else:
                    print(f"Failed to fetch works for {openalex_id}: {response.status_code} - {response.text}")
                    if response.status_code == 429:  # Rate limit exceeded
                        delay = min(delay * 2, MAX_BACKOFF_DELAY)
                        print(f"Rate limit exceeded, retrying in {delay} seconds")
                        time.sleep(delay)
                    break

            if requests_made == 0:
                break  # No more pages to fetch

            # Introduce a delay to avoid hitting the rate limit
            time.sleep(delay)

        # Step 4: Extract domain, field, and subfield from works
        result = []
        for work in works:
            if 'topics' in work and work['topics']:
                for topic in work['topics']:
                    # Extract the domain, field, and subfield information
                    domain_name = topic.get('domain', {}).get('display_name', 'Unknown Domain')
                    field_name = topic.get('field', {}).get('display_name', 'Unknown Field')
                    subfield_name = topic.get('subfield', {}).get('display_name', 'Unknown Subfield')
                    
                    # Add to result list
                    result.append({
                        'domain': domain_name,
                        'field': field_name,
                        'subfield': subfield_name
                    })

                    # Step 5: Create domain, field, and subfield nodes and relationships
                    # Create domain node if it doesn't exist
                    self.graph.create_domain_node(
                        domain_id=domain_name,  # Assuming domain name as ID
                        name=domain_name
                    )
                    # Create relationship between the expert and the domain
                    self.graph.create_related_to_relationship(orcid, domain_name)
                    
                    # Create field node if it doesn't exist
                    self.graph.create_field_node(
                        field_id=field_name,  # Assuming field name as ID
                        name=field_name
                    )
                    # Create relationship between the expert and the field
                    self.graph.create_related_to_field_relationship(orcid, field_name)
                    
                    # Create subfield node if it doesn't exist
                    if subfield_name != 'Unknown Subfield':  # Only create if there is a valid subfield
                        self.graph.create_subfield_node(
                            subfield_id=subfield_name,  # Assuming subfield name as ID
                            name=subfield_name
                        )
                        # Create relationship between the expert and the subfield
                        self.graph.create_related_to_subfield_relationship(orcid, subfield_name)

        # Step 6: Calculate expert similarity
        self.graph.calculate_similar_experts(orcid)

        return expert_data