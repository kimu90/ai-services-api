import logging
from neo4j import GraphDatabase, Session, Driver
from typing import List, Dict, Any
from contextlib import contextmanager
from ai_services_api.services.recommendation.config import get_settings

class GraphDatabase:
    def __init__(self):
        settings = get_settings()
        self._driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
        )
        self._logger = logging.getLogger(__name__)
        self._create_indexes()

    @contextmanager
    def _get_session(self) -> Session:
        """Context manager for Neo4j session handling"""
        session = None
        try:
            session = self._driver.session()
            yield session
        except Exception as e:
            self._logger.error(f"Neo4j session error: {e}")
            raise
        finally:
            if session:
                session.close()

    def _create_indexes(self):
        """Create indexes for performance optimization"""
        index_queries = [
            "CREATE INDEX expert_orcid IF NOT EXISTS FOR (e:Expert) ON (e.orcid)",
            "CREATE INDEX field_name IF NOT EXISTS FOR (f:Field) ON (f.name)",
            "CREATE INDEX subfield_name IF NOT EXISTS FOR (sf:Subfield) ON (sf.name)",
            "CREATE INDEX domain_name IF NOT EXISTS FOR (d:Domain) ON (d.name)"
        ]
        
        with self._get_session() as session:
            for query in index_queries:
                try:
                    session.run(query)
                    self._logger.info(f"Index created: {query}")
                except Exception as e:
                    self._logger.warning(f"Error creating index: {e}")

    def create_expert_node(self, orcid: str, name: str):
        """Create or update an expert node"""
        with self._get_session() as session:
            try:
                session.run(
                    "MERGE (e:Expert {orcid: $orcid}) "
                    "ON CREATE SET e.name = $name "
                    "ON MATCH SET e.name = $name", 
                    {"orcid": orcid, "name": name}
                )
            except Exception as e:
                self._logger.error(f"Error creating expert node: {e}")
                raise

    def create_domain_node(self, domain_id: str, name: str):
        """Create a domain node"""
        with self._get_session() as session:
            try:
                session.run(
                    "MERGE (d:Domain {name: $name}) "
                    "SET d.domain_id = $domain_id", 
                    {"name": name, "domain_id": domain_id}
                )
            except Exception as e:
                self._logger.error(f"Error creating domain node: {e}")
                raise

    def create_field_node(self, field_id: str, name: str):
        """Create a field node"""
        with self._get_session() as session:
            try:
                session.run(
                    "MERGE (f:Field {name: $name}) "
                    "SET f.field_id = $field_id", 
                    {"name": name, "field_id": field_id}
                )
            except Exception as e:
                self._logger.error(f"Error creating field node: {e}")
                raise

    def create_subfield_node(self, subfield_id: str, name: str):
        """Create a subfield node"""
        with self._get_session() as session:
            try:
                session.run(
                    "MERGE (sf:Subfield {name: $name}) "
                    "SET sf.subfield_id = $subfield_id", 
                    {"name": name, "subfield_id": subfield_id}
                )
            except Exception as e:
                self._logger.error(f"Error creating subfield node: {e}")
                raise

    def create_related_to_relationship(self, orcid: str, target_name: str):
        """Create a RELATED_TO relationship"""
        with self._get_session() as session:
            try:
                session.run(
                    """
                    MATCH (e:Expert {orcid: $orcid})
                    MATCH (target {name: $target_name})
                    MERGE (e)-[:RELATED_TO]->(target)
                    """, 
                    {"orcid": orcid, "target_name": target_name}
                )
            except Exception as e:
                self._logger.error(f"Error creating relationship: {e}")
                raise

    def query_graph(self, query: str, parameters: Dict[str, Any] = None):
        """Execute a Cypher query with optional parameters"""
        with self._get_session() as session:
            try:
                result = session.run(query, parameters or {})
                return [record for record in result]
            except Exception as e:
                self._logger.error(f"Graph query error: {e}")
                raise

    def get_graph_stats(self) -> Dict[str, int]:
        """Get comprehensive graph statistics"""
        with self._get_session() as session:
            try:
                stats = {
                    "expert_count": session.run("MATCH (e:Expert) RETURN count(e)").single()[0],
                    "domain_count": session.run("MATCH (d:Domain) RETURN count(d)").single()[0],
                    "field_count": session.run("MATCH (f:Field) RETURN count(f)").single()[0],
                    "subfield_count": session.run("MATCH (sf:Subfield) RETURN count(sf)").single()[0],
                    "relationship_count": session.run("MATCH ()-->() RETURN count(*) as rel_count").single()[0]
                }
                return stats
            except Exception as e:
                self._logger.error(f"Error getting graph stats: {e}")
                return {}

    def close(self):
        """Close the Neo4j driver connection"""
        if self._driver:
            self._driver.close()