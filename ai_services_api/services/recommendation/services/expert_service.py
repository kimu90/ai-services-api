from ai_services_api.services.recommendation.core.database import GraphDatabase  # Changed from RedisGraph
from ai_services_api.services.recommendation.services.openalex_service import OpenAlexService
from ai_services_api.services.recommendation.schemas.expert import SimilarExpert


class ExpertService:
    def __init__(self):
        # Initialize the graph database and OpenAlex service
        self.graph = GraphDatabase()
        self.openalex = OpenAlexService()

    async def add_expert(self, orcid: str):
        """Add or update an expert in the graph database with domain relationships"""
        
        # Prepend the base URL to the ORCID
        orcid_url = f"https://orcid.org/{orcid}"

        # Fetch expert data from OpenAlex using the ORCID URL
        expert_data = await self.openalex.get_expert_data(orcid_url)
        
        # If no expert data is found, return None
        if not expert_data:
            return None

        # Create or update expert node with ORCID URL and display name
        self.graph.create_expert_node(
            orcid=orcid_url,
            name=expert_data.get('display_name', 'No name provided')
        )

        # Get domains related to the expert
        domains = await self.openalex.get_expert_domains(orcid_url)

        for domain in domains:
            # Create domain node if it doesn't exist
            self.graph.create_domain_node(
                domain_id=domain['id'],
                name=domain['display_name']
            )

            # Create relationship between the expert and the domain
            self.graph.create_related_to_relationship(orcid_url, domain['id'])

        # Calculate similarities based on shared domains
        self.graph.calculate_similar_experts(orcid_url)

        return expert_data

    def get_similar_experts(self, orcid: str, limit: int = 10):
        """Retrieve similar experts based on shared domains"""
        
        # Prepend the base URL to the ORCID for similarity check
        orcid_url = f"https://orcid.org/{orcid}"
        
        # Define the query to get similar experts from the graph
        query = """
        MATCH (e1:Expert)-[s:SIMILAR_TO]->(e2:Expert)
        WHERE e1.orcid = $orcid
        RETURN e2.orcid AS similar_orcid, e2.name AS name, s.score AS similarity_score
        ORDER BY s.score DESC
        LIMIT $limit
        """
        
        # Parameters to be used in the query
        params = {
            'orcid': orcid_url,
            'limit': limit
        }
        
        # Execute the query on the graph
        result = self.graph.graph.query(query, params)
        
        # Log the raw result to see its structure (for debugging purposes)
        print("Raw query result:", result)
        
        # Extract the result set from the QueryResult object
        result_set = result.result_set if result else []
        
        # Convert the result set into a list of SimilarExpert objects
        similar_experts = []
        for record in result_set:
            # Create SimilarExpert object directly from the record fields
            similar_experts.append(
                SimilarExpert(
                    orcid=record[0],        # similar_orcid is the first field
                    name=record[1],         # name is the second field
                    similarity_score=float(record[2])  # similarity_score is the third field
                )
            )
        
        return similar_experts