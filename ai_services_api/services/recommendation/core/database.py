import redis
from redisgraph import Graph
import requests
from ai_services_api.services.recommendation.config import get_settings

settings = get_settings()

class GraphDatabase:
    def __init__(self):
        # Use Redis Graph URL if available, otherwise fall back to host/port configuration
        if hasattr(settings, 'REDIS_GRAPH_URL') and settings.REDIS_GRAPH_URL:
            self.redis_conn = redis.from_url(settings.REDIS_GRAPH_URL, decode_responses=True)
        else:
            self.redis_conn = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
        self.graph = Graph('expert_graph', self.redis_conn)
        self.openalex_api_url = settings.OPENALEX_API_URL

    def get_author_openalex_id(self, orcid: str):
        """Fetch OpenAlex ID for an author using their ORCID."""
        response = requests.get(f"{self.openalex_api_url}/authors", params={"filter": f"orcid:{orcid}"})
        if response.status_code == 200 and response.json().get('results'):
            author_data = response.json()['results'][0]
            return author_data['id'], author_data['orcid']
        else:
            raise ValueError(f"No OpenAlex author found with ORCID: {orcid}")

    def get_author_works_by_openalex_id(self, openalex_id: str):
        """Fetch works for an author using their OpenAlex ID and extract domain information."""
        response = requests.get(f"{self.openalex_api_url}/works", params={"filter": f"authorships.author.id:{openalex_id}"})
        if response.status_code == 200:
            works = response.json().get('results', [])
            domains = []
            for work in works:
                for concept in work.get('concepts', []):
                    if concept.get('domain'):
                        domains.append(self.extract_domain_info(concept['domain']))
            return domains
        else:
            raise ValueError(f"No works found for OpenAlex author ID: {openalex_id}")

    def extract_domain_info(self, domain):
        """Extract domain details from the domain object."""
        return {
            'id': domain['id'],
            'display_name': domain['display_name']
        }

    def create_expert_node(self, orcid: str, name: str):
        """Create or update an Expert node."""
        query = """
        MERGE (e:Expert {orcid: $orcid})
        SET e.name = $name
        """
        params = {'orcid': orcid, 'name': name}
        self.graph.query(query, params)

    def create_domain_node(self, domain_id: str, name: str):
        """Create or update a Domain node."""
        query = """
        MERGE (d:Domain {id: $domain_id})
        SET d.name = $name
        """
        params = {'domain_id': domain_id, 'name': name}
        self.graph.query(query, params)

    def create_related_to_relationship(self, orcid: str, domain_id: str):
        """Create a RELATED_TO relationship between Expert and Domain."""
        query = """
        MATCH (e:Expert {orcid: $orcid})
        MATCH (d:Domain {id: $domain_id})
        MERGE (e)-[r:RELATED_TO]->(d)
        """
        params = {'orcid': orcid, 'domain_id': domain_id}
        self.graph.query(query, params)

    def calculate_similar_experts(self, orcid: str):
        """Calculate similarity between experts based on shared domains."""
        query = """
        MATCH (e1:Expert {orcid: $orcid})-[:RELATED_TO]->(d:Domain)<-[:RELATED_TO]-(e2:Expert)
        WHERE e1 <> e2
        WITH e1, e2, COUNT(d) as shared_domains
        MATCH (e2)-[:RELATED_TO]->(d:Domain)
        WITH e1, e2, shared_domains, COUNT(d) as total_domains
        WITH e1, e2, shared_domains, total_domains,
             (1.0 * shared_domains / total_domains) as similarity_score
        MERGE (e1)-[s:SIMILAR_TO]->(e2)
        SET s.score = similarity_score
        """
        params = {'orcid': orcid}
        self.graph.query(query, params)

    def get_graph_stats(self):
        """Get basic statistics about the graph."""
        stats = {
            'expert_count': 0,
            'topic_count': 0,
            'relationship_count': 0
        }
        
        # Count Expert nodes
        query = "MATCH (e:Expert) RETURN COUNT(e) as count"
        result = self.graph.query(query)
        stats['expert_count'] = result.result_set[0][0]
        
        # Count Domain nodes
        query = "MATCH (d:Domain) RETURN COUNT(d) as count"
        result = self.graph.query(query)
        stats['topic_count'] = result.result_set[0][0]
        
        # Count relationships
        query = "MATCH ()-[r]->() RETURN COUNT(r) as count"
        result = self.graph.query(query)
        stats['relationship_count'] = result.result_set[0][0]
        
        return stats