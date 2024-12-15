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
            # Record start time for analytics
            start_time = time.time()

            # Step 1: Fetch OpenAlex Expert Data
            expert_data = await self.openalex.get_expert_data(orcid)
            if not expert_data:
                return None

            # Step 2: Get domains and fields with analytics tracking
            domains_fields_subfields = await self.openalex.get_expert_domains(orcid)
            expert_data['domains_fields_subfields'] = domains_fields_subfields

            # Step 3: Insert into PostgreSQL with analytics
            cursor = self.db_conn.cursor()
            try:
                # Insert expert data
                insert_expert(self.db_conn, expert_data)

                # Record domain analytics
                for domain_info in domains_fields_subfields:
                    cursor.execute("""
                        INSERT INTO domain_expertise_analytics (
                            domain_name,
                            field_name,
                            subfield_name,
                            expert_count
                        ) VALUES (%s, %s, %s, 1)
                        ON CONFLICT (domain_name) DO UPDATE SET
                            expert_count = domain_expertise_analytics.expert_count + 1,
                            last_updated = CURRENT_TIMESTAMP
                    """, (
                        domain_info['domain'],
                        domain_info.get('field'),
                        domain_info.get('subfield')
                    ))

                self.db_conn.commit()
            except Exception as e:
                self.db_conn.rollback()
                raise
            finally:
                cursor.close()

            # Step 4: Create Neo4j Graph with enhanced relationships
            self.graph.create_expert_node(
                orcid=orcid,
                name=expert_data.get('display_name', ''),
                metadata={
                    'total_domains': len(domains_fields_subfields),
                    'processed_at': datetime.utcnow().isoformat()
                }
            )

            # Step 5: Process domains with relationship strength
            for domain_info in domains_fields_subfields:
                # Create nodes with metadata
                self.graph.create_domain_node(
                    domain_info['domain'],
                    domain_info['domain'],
                    metadata={'type': 'domain', 'level': 1}
                )
                self.graph.create_field_node(
                    domain_info['field'],
                    domain_info['field'],
                    metadata={'type': 'field', 'level': 2}
                )
                if domain_info['subfield']:
                    self.graph.create_subfield_node(
                        domain_info['subfield'],
                        domain_info['subfield'],
                        metadata={'type': 'subfield', 'level': 3}
                    )

                # Create weighted relationships
                self.graph.create_related_to_relationship(
                    orcid,
                    domain_info['domain'],
                    'WORKS_IN_DOMAIN',
                    properties={'weight': 1.0, 'level': 'primary'}
                )
                self.graph.create_related_to_relationship(
                    orcid,
                    domain_info['field'],
                    'WORKS_IN_FIELD',
                    properties={'weight': 0.7, 'level': 'secondary'}
                )
                if domain_info['subfield']:
                    self.graph.create_related_to_relationship(
                        orcid,
                        domain_info['subfield'],
                        'WORKS_IN_SUBFIELD',
                        properties={'weight': 0.5, 'level': 'tertiary'}
                    )

            # Step 6: Get enhanced recommendations with analytics
            recommendations = await self.get_similar_experts(orcid)

            # Record processing metrics
            processing_time = time.time() - start_time
            cursor = self.db_conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO expert_processing_logs (
                        expert_id,
                        processing_time,
                        domains_count,
                        fields_count,
                        success
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    orcid,
                    processing_time,
                    len(domains_fields_subfields),
                    len(set(d['field'] for d in domains_fields_subfields)),
                    True
                ))
                self.db_conn.commit()
            finally:
                cursor.close()

            return {
                "expert_data": expert_data,
                "domains_fields_subfields": domains_fields_subfields,
                "recommendations": recommendations,
                "analytics": {
                    "processing_time": processing_time,
                    "domains_processed": len(domains_fields_subfields),
                    "recommendations_found": len(recommendations)
                }
            }

        except Exception as e:
            self.logger.error(f"Error in add_expert: {e}")
            # Record error in analytics
            cursor = self.db_conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO expert_processing_logs (
                        expert_id,
                        processing_time,
                        success,
                        error_message
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    orcid,
                    time.time() - start_time,
                    False,
                    str(e)
                ))
                self.db_conn.commit()
            finally:
                cursor.close()
            return None
    async def _process_expert_works(self, expert_data: Dict[str, Any]) -> List[Dict[str, str]]:
        # [Previous code remains the same]
        pass

    async def get_similar_experts(self, orcid: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Enhanced similar experts search with detailed metrics."""
        query = """
        MATCH (e1:Expert {orcid: $orcid})
        MATCH (e2:Expert)
        WHERE e1 <> e2

        // Calculate domain overlap with weights
        OPTIONAL MATCH (e1)-[r1:WORKS_IN_DOMAIN]->(d:Domain)<-[r2:WORKS_IN_DOMAIN]-(e2)
        WITH e1, e2, 
             COLLECT(DISTINCT {
                 domain: d.name,
                 weight: r1.weight * r2.weight
             }) as shared_domains,
             SUM(r1.weight * r2.weight) as domain_score

        // Calculate field overlap
        OPTIONAL MATCH (e1)-[rf1:WORKS_IN_FIELD]->(f:Field)<-[rf2:WORKS_IN_FIELD]-(e2)
        WITH e1, e2, shared_domains, domain_score,
             COLLECT(DISTINCT f.name) as shared_fields,
             SUM(rf1.weight * rf2.weight) as field_score

        // Calculate total similarity score
        WITH e2, 
             shared_domains,
             shared_fields,
             (domain_score * 0.6 + field_score * 0.4) as similarity_score
        WHERE similarity_score > 0

        RETURN {
            orcid: e2.orcid,
            name: e2.name,
            shared_domains: [d in shared_domains | d.domain],
            shared_fields: shared_fields,
            similarity_score: similarity_score,
            metrics: {
                domain_count: size(shared_domains),
                field_count: size(shared_fields),
                total_overlap: size(shared_domains) + size(shared_fields)
            }
        } as result
        ORDER BY similarity_score DESC
        LIMIT $limit
        """

        try:
            start_time = time.time()
            parameters = {'orcid': orcid, 'limit': limit}
            result = self.graph.query_graph(query, parameters)
            similar_experts = []

            for record in result:
                expert_data = record["result"]
                similar_experts.append({
                    'orcid': expert_data['orcid'],
                    'name': expert_data['name'],
                    'similarity_score': expert_data['similarity_score'],
                    'shared_domains': expert_data['shared_domains'],
                    'shared_fields': expert_data['shared_fields'],
                    'metrics': expert_data['metrics']
                })

            # Record matching analytics
            cursor = self.db_conn.cursor()
            try:
                for expert in similar_experts:
                    cursor.execute("""
                        INSERT INTO expert_matching_logs (
                            expert_id,
                            matched_expert_id,
                            similarity_score,
                            shared_domains,
                            shared_fields,
                            successful
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        orcid,
                        expert['orcid'],
                        expert['similarity_score'],
                        len(expert['shared_domains']),
                        len(expert['shared_fields']),
                        expert['similarity_score'] >= 0.5
                    ))
                self.db_conn.commit()
            finally:
                cursor.close()

            self.logger.info(f"Found {len(similar_experts)} similar experts for {orcid}")
            return similar_experts

        except Exception as e:
            self.logger.error(f"Error finding similar experts for {orcid}: {str(e)}", exc_info=True)
            return []

    def get_expert_summary(self, orcid: str) -> Dict[str, Any]:
        """Enhanced expert summary with analytics data."""
        query = """
        MATCH (e:Expert {orcid: $orcid})
        OPTIONAL MATCH (e)-[rd:WORKS_IN_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (e)-[rf:WORKS_IN_FIELD]->(f:Field)
        OPTIONAL MATCH (e)-[rs:WORKS_IN_SUBFIELD]->(sf:Subfield)
        
        WITH e,
             COLLECT(DISTINCT {
                 name: d.name,
                 weight: rd.weight,
                 level: rd.level
             }) as domains,
             COLLECT(DISTINCT {
                 name: f.name,
                 weight: rf.weight,
                 level: rf.level
             }) as fields,
             COLLECT(DISTINCT {
                 name: sf.name,
                 weight: rs.weight,
                 level: rs.level
             }) as subfields
             
        RETURN {
            name: e.name,
            domains: domains,
            fields: fields,
            subfields: subfields,
            metrics: {
                total_domains: size(domains),
                total_fields: size(fields),
                total_subfields: size(subfields),
                expertise_depth: size(domains) + size(fields) + size(subfields)
            }
        } as summary
        """

        try:
            result = self.graph.query_graph(query, {'orcid': orcid})
            if not result:
                self.logger.warning(f"No data found for expert {orcid}")
                return {}

            summary = result[0]["summary"]
            
            # Add analytics tracking
            cursor = self.db_conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO expert_summary_logs (
                        expert_id,
                        total_domains,
                        total_fields,
                        total_subfields,
                        expertise_depth,
                        timestamp
                    ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    orcid,
                    summary['metrics']['total_domains'],
                    summary['metrics']['total_fields'],
                    summary['metrics']['total_subfields'],
                    summary['metrics']['expertise_depth']
                ))
                self.db_conn.commit()
            finally:
                cursor.close()
            
            return summary

        except Exception as e:
            self.logger.error(f"Error generating expert summary for {orcid}: {str(e)}", exc_info=True)
            return {}
