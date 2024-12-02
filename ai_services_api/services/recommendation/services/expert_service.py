from typing import List, Dict, Any, Optional
import logging
import requests
import time
import asyncio
from ai_services_api.services.recommendation.core.database import Neo4jDatabase
from ai_services_api.services.recommendation.services.openalex_service import OpenAlexService
from ai_services_api.services.recommendation.core.postgres_database import get_db_connection, insert_expert

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Constants
INITIAL_DELAY = 1
MAX_BACKOFF_DELAY = 60
BATCH_SIZE = 5
BASE_WORKS_URL = "https://api.openalex.org/works"

class ExpertsService:
    def __init__(self):
        self.graph = Neo4jDatabase()
        self.openalex = OpenAlexService()
        self.db_conn = get_db_connection()  # PostgreSQL connection
        self.logger = logging.getLogger(__name__)

    async def add_expert(self, orcid: str) -> Optional[Dict[str, Any]]:
        try:
            # Step 1: Fetch OpenAlex Expert Data
            expert_data = await self.openalex.get_expert_data(orcid)
            if not expert_data:
                return None

            # Step 2: Get domains and fields
            domains_fields_subfields = await self.openalex.get_expert_domains(orcid)
            expert_data['domains_fields_subfields'] = domains_fields_subfields

            # Step 3: Insert into PostgreSQL
            insert_expert(self.db_conn, expert_data)

            # Step 4: Create Neo4j Graph
            self.graph.create_expert_node(
                orcid=orcid,
                name=expert_data.get('display_name', '')
            )

            # Step 5: Process domains for graph
            for domain_info in domains_fields_subfields:
                # Create nodes
                self.graph.create_domain_node(domain_info['domain'], domain_info['domain'])
                self.graph.create_field_node(domain_info['field'], domain_info['field'])
                if domain_info['subfield']:
                    self.graph.create_subfield_node(domain_info['subfield'], domain_info['subfield'])

                # Create relationships
                self.graph.create_related_to_relationship(orcid, domain_info['domain'], 'WORKS_IN_DOMAIN')
                self.graph.create_related_to_relationship(orcid, domain_info['field'], 'WORKS_IN_FIELD')
                if domain_info['subfield']:
                    self.graph.create_related_to_relationship(orcid, domain_info['subfield'], 'WORKS_IN_SUBFIELD')

            # Step 6: Get recommendations
            recommendations = self.get_similar_experts(orcid)

            return {
                "expert_data": expert_data,
                "domains_fields_subfields": domains_fields_subfields,
                "recommendations": recommendations
            }

        except Exception as e:
            self.logger.error(f"Error in add_expert: {e}")
            return None
    async def _process_expert_works(self, expert_data: Dict[str, Any]) -> List[Dict[str, str]]:
        # [Previous code remains the same]
        pass

    def get_similar_experts(self, orcid: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find similar experts based on shared domains
        """
        query = """
        MATCH (e1:Expert {orcid: $orcid})-[:WORKS_IN_DOMAIN]->(d:Domain)<-[:WORKS_IN_DOMAIN]-(e2:Expert)
        WHERE e1 <> e2
        WITH e2, 
            COUNT(DISTINCT d) as shared_domains,
            COLLECT(DISTINCT d.name) as domain_names
        RETURN 
            e2.orcid AS similar_orcid,
            e2.name AS name,
            shared_domains,
            domain_names,
            toFloat(shared_domains) AS similarity_score
        ORDER BY similarity_score DESC
        LIMIT $limit
        """

        try:
            parameters = {'orcid': orcid, 'limit': limit}
            result = self.graph.query_graph(query, parameters)
            similar_experts = []

            for record in result:
                expert = {
                    'orcid': record[0],
                    'name': record[1],
                    'shared_domain_count': record[2],
                    'shared_domains': record[3],
                    'similarity_score': record[4]
                }
                similar_experts.append(expert)

            self.logger.info(f"Found {len(similar_experts)} similar experts for {orcid}")
            return similar_experts

        except Exception as e:
            self.logger.error(f"Error finding similar experts for {orcid}: {str(e)}", exc_info=True)
            return []

    def get_expert_summary(self, orcid: str) -> Dict[str, Any]:
        """
        Get a summary of an expert's domains and relationships
        """
        self.logger.info(f"Generating summary for expert: {orcid}")
        
        query = """
        MATCH (e:Expert {orcid: $orcid})
        OPTIONAL MATCH (e)-[:WORKS_IN_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (e)-[:WORKS_IN_FIELD]->(f:Field)
        OPTIONAL MATCH (e)-[:WORKS_IN_SUBFIELD]->(sf:Subfield)
        RETURN 
            e.name AS name,
            COLLECT(DISTINCT d.name) AS domains,
            COLLECT(DISTINCT f.name) AS fields,
            COLLECT(DISTINCT sf.name) AS subfields
        """

        try:
            result = self.graph.query_graph(query, {'orcid': orcid})
            if not result:
                self.logger.warning(f"No data found for expert {orcid}")
                return {}

            record = result[0]
            summary = {
                'name': record[0],
                'domains': record[1],
                'fields': record[2],
                'subfields': record[3]
            }
            
            self.logger.info(f"Successfully generated summary for {orcid}")
            return summary

        except Exception as e:
            self.logger.error(f"Error generating expert summary for {orcid}: {str(e)}", exc_info=True)
            return {}