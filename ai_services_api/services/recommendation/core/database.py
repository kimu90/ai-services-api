import logging
from neo4j import GraphDatabase as Neo4jDriver
from typing import List, Dict, Any
from contextlib import contextmanager
from ai_services_api.services.recommendation.config import get_settings

class Neo4jDatabase:
   def __init__(self):
       settings = get_settings()
       self._driver = Neo4jDriver.driver(
           settings.NEO4J_URI, 
           auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
       )
       self._logger = logging.getLogger(__name__)
       self._create_indexes()

   @contextmanager
   def _get_session(self) -> 'Session':
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
       """
       Create or update an expert node
       Args:
           orcid (str): Expert's ORCID identifier
           name (str): Expert's full name
       """
       with self._get_session() as session:
           try:
               session.run(
                   """
                   MERGE (e:Expert {orcid: $orcid}) 
                   ON CREATE SET e.name = $name 
                   ON MATCH SET e.name = $name
                   """, 
                   {"orcid": orcid, "name": name}
               )
               self._logger.info(f"Created/updated expert node for {orcid} with name {name}")
           except Exception as e:
               self._logger.error(f"Error creating expert node for {orcid}: {e}")
               raise

   def create_domain_node(self, domain_id: str, name: str):
       """
       Create a domain node
       Args:
           domain_id (str): Unique identifier for the domain
           name (str): Domain name
       """
       with self._get_session() as session:
           try:
               session.run(
                   """
                   MERGE (d:Domain {name: $name})
                   ON CREATE SET d.domain_id = $domain_id
                   ON MATCH SET d.domain_id = $domain_id
                   """, 
                   {"name": name, "domain_id": domain_id}
               )
               self._logger.info(f"Created/updated domain node: {name}")
           except Exception as e:
               self._logger.error(f"Error creating domain node {name}: {e}")
               raise

   def create_field_node(self, field_id: str, name: str):
       """
       Create a field node
       Args:
           field_id (str): Unique identifier for the field
           name (str): Field name
       """
       with self._get_session() as session:
           try:
               session.run(
                   """
                   MERGE (f:Field {name: $name})
                   ON CREATE SET f.field_id = $field_id
                   ON MATCH SET f.field_id = $field_id
                   """, 
                   {"name": name, "field_id": field_id}
               )
               self._logger.info(f"Created/updated field node: {name}")
           except Exception as e:
               self._logger.error(f"Error creating field node {name}: {e}")
               raise

   def create_subfield_node(self, subfield_id: str, name: str):
       """
       Create a subfield node
       Args:
           subfield_id (str): Unique identifier for the subfield
           name (str): Subfield name
       """
       with self._get_session() as session:
           try:
               session.run(
                   """
                   MERGE (sf:Subfield {name: $name})
                   ON CREATE SET sf.subfield_id = $subfield_id
                   ON MATCH SET sf.subfield_id = $subfield_id
                   """, 
                   {"name": name, "subfield_id": subfield_id}
               )
               self._logger.info(f"Created/updated subfield node: {name}")
           except Exception as e:
               self._logger.error(f"Error creating subfield node {name}: {e}")
               raise

   def create_related_to_relationship(self, orcid: str, target_name: str, relationship_type: str):
       """
       Create a relationship between expert and target node
       Args:
           orcid (str): Expert's ORCID identifier
           target_name (str): Name of the target node
           relationship_type (str): Type of relationship (WORKS_IN_DOMAIN, WORKS_IN_FIELD, WORKS_IN_SUBFIELD)
       """
       with self._get_session() as session:
           try:
               # Determine the target node label based on relationship type
               target_label = {
                   'WORKS_IN_DOMAIN': 'Domain',
                   'WORKS_IN_FIELD': 'Field',
                   'WORKS_IN_SUBFIELD': 'Subfield'
               }.get(relationship_type)

               if not target_label:
                   raise ValueError(f"Invalid relationship type: {relationship_type}")

               query = f"""
               MATCH (e:Expert {{orcid: $orcid}})
               MATCH (t:{target_label} {{name: $target_name}})
               MERGE (e)-[r:{relationship_type}]->(t)
               """
               
               session.run(query, {
                   "orcid": orcid,
                   "target_name": target_name
               })
               
               self._logger.info(f"Created relationship {relationship_type} from {orcid} to {target_name}")
           except Exception as e:
               self._logger.error(f"Error creating relationship: {e}")
               raise

   def query_graph(self, query: str, parameters: Dict[str, Any] = None) -> List[Any]:
       """
       Execute a Cypher query with optional parameters
       Args:
           query (str): Cypher query to execute
           parameters (Dict[str, Any], optional): Query parameters
       Returns:
           List[Any]: Query results
       """
       with self._get_session() as session:
           try:
               result = session.run(query, parameters or {})
               return [record for record in result]
           except Exception as e:
               self._logger.error(f"Graph query error: {e}")
               raise

   def get_graph_stats(self) -> Dict[str, int]:
       """
       Get comprehensive graph statistics
       Returns:
           Dict[str, int]: Statistics about nodes and relationships
       """
       with self._get_session() as session:
           try:
               stats = {
                   "expert_count": session.run("MATCH (e:Expert) RETURN count(e)").single()[0],
                   "domain_count": session.run("MATCH (d:Domain) RETURN count(d)").single()[0],
                   "field_count": session.run("MATCH (f:Field) RETURN count(f)").single()[0],
                   "subfield_count": session.run("MATCH (sf:Subfield) RETURN count(sf)").single()[0],
                   "relationship_count": session.run("MATCH ()-->() RETURN count(*) as rel_count").single()[0]
               }
               self._logger.info(f"Retrieved graph statistics: {stats}")
               return stats
           except Exception as e:
               self._logger.error(f"Error getting graph stats: {e}")
               return {}

   def clear_graph(self):
       """Clear all nodes and relationships from the graph"""
       with self._get_session() as session:
           try:
               session.run("MATCH (n) DETACH DELETE n")
               self._logger.info("Cleared all nodes and relationships from the graph")
           except Exception as e:
               self._logger.error(f"Error clearing graph: {e}")
               raise

   def close(self):
       """Close the Neo4j driver connection"""
       if self._driver:
           try:
               self._driver.close()
               self._logger.info("Closed Neo4j driver connection")
           except Exception as e:
               self._logger.error(f"Error closing Neo4j connection: {e}")