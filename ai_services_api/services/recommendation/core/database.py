import logging
import os
from typing import Optional, List, Dict, Any
from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable, AuthError
import backoff
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GraphDatabase:
    def __init__(self, max_retries: int = 5):
        """
        Initialize Neo4j connection with retry logic.
        
        Args:
            max_retries: Maximum number of connection attempts.
        """
        self.max_retries = max_retries
        self.neo4j_uri = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
        self.neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')
        self.openalex_api_url = os.getenv('OPENALEX_API_URL', 'https://api.openalex.org')
        self.driver = None
        self._initialize_connection()

    @backoff.on_exception(
        backoff.expo,
        (ServiceUnavailable, AuthError),
        max_tries=5,
        max_time=30
    )
    def _initialize_connection(self) -> None:
        """Initialize Neo4j connection with exponential backoff retry logic."""
        try:
            logger.info(f"Attempting to connect to Neo4j at {self.neo4j_uri}")
            # Correct connection setup
            self.driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"Successfully connected to Neo4j at {self.neo4j_uri}")
        except Exception as e:
            logger.error(f"Neo4j connection error: {str(e)}")
            raise

    def get_connection_info(self) -> dict:
        """Get current connection information."""
        if not self.driver:
            return {'status': 'disconnected'}
            
        return {
            'uri': self.neo4j_uri,
            'user': self.neo4j_user,
            'status': 'connected' if self._test_connection() else 'disconnected'
        }

    def _test_connection(self) -> bool:
        """Test Neo4j connection."""
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception as e:
            logger.error(f"Failed to test Neo4j connection: {str(e)}")
            return False

    def ensure_connection(self) -> None:
        """Ensure Neo4j connection is alive."""
        if not self.driver or not self._test_connection():
            logger.warning("Neo4j connection lost, attempting to reconnect...")
            self._initialize_connection()

    def query_graph(self, query: str, parameters: Optional[dict] = None) -> List[Any]:
        """Execute a graph query with connection check and retries."""
        self.ensure_connection()
        
        @backoff.on_exception(
            backoff.expo,
            ServiceUnavailable,
            max_tries=3
        )
        def execute_query():
            try:
                with self.driver.session() as session:
                    result = session.run(query, parameters or {})
                    return [record for record in result]
            except Exception as e:
                logger.error(f"Error executing Neo4j query: {str(e)}")
                raise

        return execute_query()

    def create_expert_node(self, orcid: str, name: str):
        """Create or update an Expert node."""
        query = """
        MERGE (e:Expert {orcid: $orcid})
        SET e.name = $name
        """
        self.query_graph(query, {'orcid': orcid, 'name': name})
        logger.info(f"Expert node created or updated for ORCID: {orcid}")

    # Additional methods (create_domain_node, create_field_node, etc.) remain unchanged.


    def create_domain_node(self, domain_id: str, name: str):
        """Create or update a Domain node."""
        query = """
        MERGE (d:Domain {id: $domain_id})
        SET d.name = $name
        """
        self.query_graph(query, {'domain_id': domain_id, 'name': name})
        logger.info(f"Domain node created or updated for domain ID: {domain_id}")

    def create_field_node(self, field_id: str, name: str):
        """Create or update a Field node."""
        query = """
        MERGE (f:Field {id: $field_id})
        SET f.name = $name
        """
        self.query_graph(query, {'field_id': field_id, 'name': name})
        logger.info(f"Field node created or updated for field ID: {field_id}")

    def create_subfield_node(self, subfield_id: str, name: str):
        """Create or update a Subfield node."""
        query = """
        MERGE (sf:Subfield {id: $subfield_id})
        SET sf.name = $name
        """
        self.query_graph(query, {'subfield_id': subfield_id, 'name': name})
        logger.info(f"Subfield node created or updated for subfield ID: {subfield_id}")

    def create_related_to_relationship(self, orcid: str, target_id: str):
        """Create a RELATED_TO relationship between Expert and another node."""
        query = """
        MATCH (e:Expert {orcid: $orcid})
        MATCH (n {id: $target_id})
        WHERE n:Domain OR n:Field OR n:Subfield
        MERGE (e)-[r:RELATED_TO]->(n)
        """
        self.query_graph(query, {'orcid': orcid, 'target_id': target_id})
        logger.info(f"RELATED_TO relationship created between Expert {orcid} and node {target_id}")

    def get_graph_stats(self) -> Dict[str, int]:
        """Get statistics about the graph database."""
        self.ensure_connection()
        
        try:
            stats = {}
            queries = {
                'Expert Count': "MATCH (e:Expert) RETURN COUNT(e) as count",
                'Domain Count': "MATCH (d:Domain) RETURN COUNT(d) as count",
                'Field Count': "MATCH (f:Field) RETURN COUNT(f) as count",
                'Subfield Count': "MATCH (sf:Subfield) RETURN COUNT(sf) as count",
                'RELATED_TO Relationships': "MATCH ()-[r:RELATED_TO]->() RETURN COUNT(r) as count"
            }
            
            for key, query in queries.items():
                result = self.query_graph(query)
                stats[key] = result[0][0] if result else 0

            return stats

        except Exception as e:
            logger.error(f"Error getting graph stats: {str(e)}")
            return {}

    def close(self):
        """Close the Neo4j driver connection"""
        if self.driver:
            self.driver.close()

# Instantiate GraphDatabase class
graph_db = GraphDatabase()