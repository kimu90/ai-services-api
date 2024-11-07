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
        self.graph = Graph('reco_graph', self.redis_conn)
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
        """Fetch works for an author using their OpenAlex ID and extract domain, field, and subfield information."""
        response = requests.get(f"{self.openalex_api_url}/works", params={"filter": f"authorships.author.id:{openalex_id}"})
        if response.status_code == 200:
            works = response.json().get('results', [])
            topics_info = []
            for work in works:
                for topic in work.get('topics', []):
                    domain = topic.get('domain')
                    field = topic.get('field')
                    subfield = topic.get('subfield')
                    
                    # Append the topic information if at least one of domain, field, or subfield is present
                    if domain or field or subfield:
                        topics_info.append({
                            'domain': self.extract_domain_info(domain) if domain else None,
                            'field': self.extract_field_info(field) if field else None,
                            'subfield': self.extract_subfield_info(subfield) if subfield else None
                        })
            return topics_info
        else:
            raise ValueError(f"No works found for OpenAlex author ID: {openalex_id}")

    def extract_domain_info(self, domain):
        """Extract domain details from the domain object."""
        return {
            'id': domain['id'],
            'display_name': domain['display_name']
        }

    def extract_field_info(self, field):
        """Extract field details from the field object."""
        return {
            'id': field['id'],
            'display_name': field['display_name']
        }

    def extract_subfield_info(self, subfield):
        """Extract subfield details from the subfield object."""
        return {
            'id': subfield['id'],
            'display_name': subfield['display_name']
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

    def create_field_node(self, field_id: str, name: str):
        """Create or update a Field node."""
        query = """
        MERGE (f:Field {id: $field_id})
        SET f.name = $name
        """
        params = {'field_id': field_id, 'name': name}
        self.graph.query(query, params)

    def create_subfield_node(self, subfield_id: str, name: str):
        """Create or update a Subfield node."""
        query = """
        MERGE (sf:Subfield {id: $subfield_id})
        SET sf.name = $name
        """
        params = {'subfield_id': subfield_id, 'name': name}
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

    def create_related_to_field_relationship(self, orcid: str, field_id: str):
        """Create a RELATED_TO relationship between Expert and Field."""
        query = """
        MATCH (e:Expert {orcid: $orcid})
        MATCH (f:Field {id: $field_id})
        MERGE (e)-[r:RELATED_TO]->(f)
        """
        params = {'orcid': orcid, 'field_id': field_id}
        self.graph.query(query, params)

    def create_related_to_subfield_relationship(self, orcid: str, subfield_id: str):
        """Create a RELATED_TO relationship between Expert and Subfield."""
        query = """
        MATCH (e:Expert {orcid: $orcid})
        MATCH (sf:Subfield {id: $subfield_id})
        MERGE (e)-[r:RELATED_TO]->(sf)
        """
        params = {'orcid': orcid, 'subfield_id': subfield_id}
        self.graph.query(query, params)

    def add_expert(self, orcid: str, name: str):
        """Add an expert and related topics to the graph."""
        # Create or update Expert node
        self.create_expert_node(orcid, name)

        # Fetch OpenAlex ID and Works
        openalex_id, _ = self.get_author_openalex_id(orcid)
        topics_info = self.get_author_works_by_openalex_id(openalex_id)

        # Create or update Domain, Field, and Subfield nodes, and relationships
        for topic in topics_info:
            if topic['domain']:
                self.create_domain_node(topic['domain']['id'], topic['domain']['display_name'])
                self.create_related_to_relationship(orcid, topic['domain']['id'])
            if topic['field']:
                self.create_field_node(topic['field']['id'], topic['field']['display_name'])
                self.create_related_to_field_relationship(orcid, topic['field']['id'])
            if topic['subfield']:
                self.create_subfield_node(topic['subfield']['id'], topic['subfield']['display_name'])
                self.create_related_to_subfield_relationship(orcid, topic['subfield']['id'])

    def calculate_similar_experts(self, orcid: str):
        """Calculate similarity between experts based on shared domains, fields, and subfields."""
        query = """
        MATCH (e1:Expert {orcid: $orcid})
        OPTIONAL MATCH (e1)-[:RELATED_TO]->(d:Domain)<-[:RELATED_TO]-(e2:Expert)
        OPTIONAL MATCH (e1)-[:RELATED_TO]->(f:Field)<-[:RELATED_TO]-(e2)
        OPTIONAL MATCH (e1)-[:RELATED_TO]->(sf:Subfield)<-[:RELATED_TO]-(e2)
        WHERE e1 <> e2
        WITH e1, e2, 
            COUNT(DISTINCT d) AS shared_domains, 
            COUNT(DISTINCT f) AS shared_fields,
            COUNT(DISTINCT sf) AS shared_subfields
        WITH e1, e2, shared_domains, shared_fields, shared_subfields,
            (shared_domains + shared_fields + shared_subfields) AS total_shared,
            (shared_domains + shared_fields + shared_subfields) * 1.0 / 
            CASE WHEN (shared_domains + shared_fields + shared_subfields) = 0 THEN 1 ELSE (shared_domains + shared_fields + shared_subfields) END AS similarity_score
        RETURN e1, e2, shared_domains, shared_fields, shared_subfields, total_shared, similarity_score
        """
        params = {'orcid': orcid}
        self.graph.query(query, params)

    def get_graph_stats(self):
        """Get basic statistics about the graph, including experts, domains, fields, subfields, and relationships."""
        stats = {
            'expert_count': 0,
            'domain_count': 0,
            'field_count': 0,
            'subfield_count': 0,
            'relationship_count': 0
        }
        # Count nodes
        expert_count = self.graph.query("MATCH (e:Expert) RETURN COUNT(e) AS count").result_set[0][0]
        domain_count = self.graph.query("MATCH (d:Domain) RETURN COUNT(d) AS count").result_set[0][0]
        field_count = self.graph.query("MATCH (f:Field) RETURN COUNT(f) AS count").result_set[0][0]
        subfield_count = self.graph.query("MATCH (sf:Subfield) RETURN COUNT(sf) AS count").result_set[0][0]
        # Count relationships
        relationship_count = self.graph.query("MATCH ()-[r]->() RETURN COUNT(r) AS count").result_set[0][0]

        stats['expert_count'] = expert_count
        stats['domain_count'] = domain_count
        stats['field_count'] = field_count
        stats['subfield_count'] = subfield_count
        stats['relationship_count'] = relationship_count
        return stats
