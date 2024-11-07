from ai_services_api.services.recommendation.core.database import GraphDatabase  # Changed from RedisGraph
from ai_services_api.services.recommendation.services.openalex_service import OpenAlexService
from ai_services_api.services.recommendation.schemas.expert import SimilarExpert


class ExpertService:
    def __init__(self):
        # Initialize the graph database and OpenAlex service
        self.graph = GraphDatabase()
        self.openalex = OpenAlexService()

    async def add_expert(self, orcid: str):
        """Add or update an expert in the graph database with domain, field, and subfield relationships"""

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

        # Get domains, fields, and subfields related to the expert
        domains = await self.openalex.get_expert_domains(orcid_url)

        for domain in domains:
            # Create domain node if it doesn't exist
            self.graph.create_domain_node(
                domain_id=domain['id'],
                name=domain['display_name']
            )

            # Create relationship between the expert and the domain
            self.graph.create_related_to_relationship(orcid_url, domain['id'])

            # Assuming fields and subfields are part of the domain data
            # Fetch fields related to this domain (this could be a separate API call or data part)
            fields = domain.get('fields', [])
            for field in fields:
                # Create field node if it doesn't exist
                self.graph.create_field_node(
                    field_id=field['id'],
                    name=field['display_name']
                )

                # Create relationship between the expert and the field
                self.graph.create_related_to_field_relationship(orcid_url, field['id'])

                # Fetch subfields for the field
                subfields = field.get('subfields', [])
                for subfield in subfields:
                    # Create subfield node if it doesn't exist
                    self.graph.create_subfield_node(
                        subfield_id=subfield['id'],
                        name=subfield['display_name']
                    )

                    # Create relationship between the expert and the subfield
                    self.graph.create_related_to_subfield_relationship(orcid_url, subfield['id'])

        # Calculate similarities based on shared domains, fields, and subfields
        self.graph.calculate_similar_experts(orcid_url)

        return expert_data


    def get_similar_experts(self, orcid: str, limit: int = 10):
        """Retrieve similar experts based on shared domains, fields, and subfields"""
        
        # Prepend the base URL to the ORCID for similarity check
        orcid_url = f"https://orcid.org/{orcid}"
        
        # Define the query to get similar experts from the graph
        query = """
        MATCH (e1:Expert)-[:RELATED_TO]->(d:Domain)<-[:RELATED_TO]-(e2:Expert)
        OPTIONAL MATCH (d)<-[:RELATED_TO]-(f:Field)<-[:RELATED_TO]-(e2)
        OPTIONAL MATCH (f)<-[:RELATED_TO]-(s:Subfield)<-[:RELATED_TO]-(e2)
        WHERE e1.orcid = $orcid
        RETURN e2.orcid AS similar_orcid, e2.name AS name, 
            COUNT(DISTINCT d) AS shared_domains, 
            COUNT(DISTINCT f) AS shared_fields, 
            COUNT(DISTINCT s) AS shared_subfields
        ORDER BY shared_domains DESC, shared_fields DESC, shared_subfields DESC
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
                    orcid=record[0],  # similar_orcid is the first field
                    name=record[1],   # name is the second field
                    similarity_score=record[2] + record[3] + record[4]  # Summing shared domains, fields, subfields
                )
            )
        
        return similar_experts
