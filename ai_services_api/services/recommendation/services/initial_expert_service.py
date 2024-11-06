from ai_services_api.services.recommendation.core.database import GraphDatabase  # Changed from RedisGraph
from ai_services_api.services.recommendation.services.openalex_service import OpenAlexService

class ExpertService:
    def __init__(self):
        self.graph = GraphDatabase()
        self.openalex = OpenAlexService()

    async def add_expert(self, orcid: str):
        """Add or update expert in RedisGraph with domain relationships"""
        expert_data = await self.openalex.get_expert_data(orcid)
        if not expert_data:
            return None

        # Create expert node with only ORCID and display name
        self.graph.create_expert_node(
            orcid=orcid,
            name=expert_data.get('display_name', '')
        )

        # Get domains related to the expert
        domains = await self.openalex.get_expert_domains(orcid)
        for domain in domains:
            self.graph.create_domain_node(
                domain_id=domain['id'],
                name=domain['display_name']
            )
            self.graph.create_related_to_relationship(orcid, domain['id'])

        # Calculate similarities based on domains
        self.graph.calculate_similar_experts(orcid)
        return expert_data

    def get_similar_experts(self, orcid: str, limit: int = 10):
        """Get similar experts based on shared domains"""
        query = """
        MATCH (e1:Expert {orcid: $orcid})-[s:SIMILAR_TO]->(e2:Expert)
        RETURN e2.orcid as orcid, e2.name as name, s.score as similarity_score
        ORDER BY s.score DESC
        LIMIT $limit
        """
        params = {
            'orcid': orcid,
            'limit': limit
        }
        return self.graph.graph.query(query, params)
