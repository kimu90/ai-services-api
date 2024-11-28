from typing import List, Dict, Any, Optional
import logging
import requests
import time
import asyncio
from ai_services_api.services.recommendation.core.database import GraphDatabase
from ai_services_api.services.recommendation.services.openalex_service import OpenAlexService

# Constants for delay and batch size
INITIAL_DELAY = 1
MAX_BACKOFF_DELAY = 60
BATCH_SIZE = 5
BASE_WORKS_URL = "https://api.openalex.org/works"

class ExpertsService:
    def __init__(self):
        self.graph = GraphDatabase()
        self.openalex = OpenAlexService()
        self.logger = logging.getLogger(__name__)

    async def add_expert(self, orcid: str):
        """Enhanced method to add expert with comprehensive recommendation"""
        try:
            # Step 1: Fetch OpenAlex Expert Data
            expert_data = await self.openalex.get_expert_data(orcid)
            if not expert_data:
                self.logger.error(f"Failed to fetch expert data for ORCID: {orcid}")
                return None

            # Step 2: Create or Update Expert Node
            self.graph.create_expert_node(
                orcid=orcid,
                name=expert_data.get('display_name', '')
            )

            # Step 3: Fetch and Process Expert's Works and Topics
            domains_fields_subfields = await self._process_expert_works(expert_data)

            # Step 4: Generate Recommendations
            recommendations = self.get_similar_experts(orcid)

            return {
                "expert_data": expert_data,
                "domains_fields_subfields": domains_fields_subfields,
                "recommendations": recommendations
            }

        except Exception as e:
            self.logger.error(f"Error adding expert {orcid}: {e}")
            return None

    async def _process_expert_works(self, expert_data):
        """Process expert's works and create graph relationships"""
        openalex_id = expert_data['id']
        domains_fields_subfields = []
        
        # Use OpenAlex service to get expert domains
        topics = await self.openalex.get_expert_domains(expert_data.get('orcid', ''))

        for topic in topics:
            domain_name = topic['domain']
            field_name = topic['field']
            subfield_name = topic['subfield']

            # Create graph nodes and relationships
            try:
                self.graph.create_domain_node(domain_id=domain_name, name=domain_name)
                self.graph.create_field_node(field_id=field_name, name=field_name)
                
                if subfield_name != 'Unknown Subfield':
                    self.graph.create_subfield_node(subfield_id=subfield_name, name=subfield_name)
                    self.graph.create_related_to_relationship(expert_data['orcid'], subfield_name)

                self.graph.create_related_to_relationship(expert_data['orcid'], domain_name)
                self.graph.create_related_to_relationship(expert_data['orcid'], field_name)

                domains_fields_subfields.append({
                    'domain': domain_name,
                    'field': field_name,
                    'subfield': subfield_name
                })

            except Exception as e:
                self.logger.error(f"Error processing topic for {expert_data['orcid']}: {e}")

        return domains_fields_subfields

    def get_similar_experts(self, orcid: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Enhanced similar experts query with scoring"""
        query = """
            MATCH (e1:Expert {orcid: $orcid})-[:RELATED_TO]->(f:Field),
                  (e1)-[:RELATED_TO]->(sf:Subfield),
                  (e2:Expert)-[:RELATED_TO]->(f),
                  (e2)-[:RELATED_TO]->(sf)
            WHERE e1 <> e2
            WITH e2, 
                 COUNT(DISTINCT f) as shared_field_count, 
                 COUNT(DISTINCT sf) as shared_subfield_count
            RETURN e2.orcid AS similar_orcid,
                   e2.name AS name,
                   shared_field_count,
                   shared_subfield_count,
                   (shared_field_count * 2 + shared_subfield_count) AS similarity_score
            ORDER BY similarity_score DESC
            LIMIT $limit
        """

        try:
            parameters = {'orcid': orcid, 'limit': limit}
            result = self.graph.query_graph(query, parameters)

            similar_experts = []
            for record in result:
                similar_experts.append({
                    'orcid': record[0],
                    'name': record[1],
                    'shared_field_count': record[2],
                    'shared_subfield_count': record[3],
                    'similarity_score': record[4]
                })

            return similar_experts

        except Exception as e:
            self.logger.error(f"Error finding similar experts for {orcid}: {e}")
            return []