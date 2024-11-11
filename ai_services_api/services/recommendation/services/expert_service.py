from typing import List, Dict, Any, Optional
import logging
import requests
import time
from ai_services_api.services.recommendation.core.database import GraphDatabase
from ai_services_api.services.recommendation.services.openalex_service import OpenAlexService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants for delay and batch size
INITIAL_DELAY = 1
MAX_BACKOFF_DELAY = 60
BATCH_SIZE = 5
BASE_WORKS_URL = "https://api.openalex.org/works"

class ExpertsService:
    def __init__(self):
        self.graph = GraphDatabase()  # Now using RedisGraph
        self.openalex = OpenAlexService()

    async def add_expert(self, orcid: str):
        """Add or update expert in the graph and retrieve similar expert recommendations."""
        # Step 1: Fetch OpenAlex ID using ORCID
        expert_data = await self.openalex.get_expert_data(orcid)
        if not expert_data:
            logger.error(f"Failed to fetch expert data for ORCID: {orcid}")
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
                    logger.error(f"Failed to fetch works for {openalex_id}: {response.status_code} - {response.text}")
                    if response.status_code == 429:  # Rate limit exceeded
                        delay = min(delay * 2, MAX_BACKOFF_DELAY)
                        logger.warning(f"Rate limit exceeded, retrying in {delay} seconds")
                        time.sleep(delay)
                    break

            if requests_made == 0:
                break  # No more pages to fetch

            # Introduce a delay to avoid hitting the rate limit
            time.sleep(delay)

        # Step 4: Extract domain, field, and subfield from works
        result = []
        seen_domains = set()  # Track already created domains
        seen_fields = set()   # Track already created fields
        seen_subfields = set()  # Track already created subfields

        for work in works:
            if 'topics' in work and work['topics']:
                for topic in work['topics']:
                    domain_name = topic.get('domain', {}).get('display_name', 'Unknown Domain')
                    field_name = topic.get('field', {}).get('display_name', 'Unknown Field')
                    subfield_name = topic.get('subfield', {}).get('display_name', 'Unknown Subfield')

                    # Add to result list
                    result.append({
                        'domain': domain_name,
                        'field': field_name,
                        'subfield': subfield_name
                    })

                    # Create nodes and relationships if not seen before
                    if domain_name not in seen_domains:
                        self.graph.create_domain_node(domain_id=domain_name, name=domain_name)
                        self.graph.create_related_to_relationship(orcid, domain_name)
                        seen_domains.add(domain_name)

                    if field_name not in seen_fields:
                        self.graph.create_field_node(field_id=field_name, name=field_name)
                        self.graph.create_related_to_relationship(orcid, field_name)
                        seen_fields.add(field_name)

                    if subfield_name != 'Unknown Subfield' and subfield_name not in seen_subfields:
                        self.graph.create_subfield_node(subfield_id=subfield_name, name=subfield_name)
                        self.graph.create_related_to_relationship(orcid, subfield_name)
                        seen_subfields.add(subfield_name)

        recommendations = self.get_similar_experts(orcid)
        return {
            "expert_data": expert_data,
            "recommendations": recommendations
        }

    def get_similar_experts(self, orcid: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get similar experts based on shared fields and subfields."""
        # Ensure the ORCID format is consistent
        if not orcid.startswith("https://orcid.org/"):
            orcid = f"https://orcid.org/{orcid}"

        query = """
            MATCH (e1:Expert {orcid: $orcid})-[:RELATED_TO]->(f:Field),
                  (e1)-[:RELATED_TO]->(sf:Subfield),
                  (e2:Expert)-[:RELATED_TO]->(f),
                  (e2)-[:RELATED_TO]->(sf)
            WHERE e1 <> e2
            RETURN e2.orcid AS similar_orcid,
                   e2.name AS name,
                   COLLECT(DISTINCT f.name) AS shared_fields,
                   COLLECT(DISTINCT sf.name) AS shared_subfields
            LIMIT $limit
        """

        try:
            parameters = {
                'orcid': orcid,
                'limit': limit
            }
            result = self.graph.query_graph(query, parameters=parameters)

            similar_experts = []
            for record in result:
                if len(record) >= 4:
                    similar_experts.append({
                        'orcid': record[0],
                        'name': record[1],
                        'shared_field': record[2],
                        'shared_subfield': record[3]
                    })
                else:
                    logger.warning(f"Unexpected record format: {record}")

            if not similar_experts:
                logger.info(f"No similar experts found for ORCID: {orcid}")

            return similar_experts

        except Exception as e:
            logger.error(f"Error executing query for ORCID {orcid}: {e}")
            return []
