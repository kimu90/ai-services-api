import logging
import redis
from redisgraph import Graph, Node
import requests
from redis import StrictRedis, ConnectionError, TimeoutError
from typing import Optional, List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv
import os
import time
import backoff
from urllib.parse import urlparse, parse_qs

load_dotenv()

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GraphDatabase:
    def __init__(self, max_retries: int = 5):
        """
        Initialize Redis connection with retry logic
        
        Args:
            max_retries: Maximum number of connection attempts
        """
        self.max_retries = max_retries
        self.redis_url = os.getenv('REDIS_GRAPH_URL', 'redis://redis-graph:6380')
        self.openalex_api_url = os.getenv('OPENALEX_API_URL', 'https://api.openalex.org')
        self.redis_client = None
        self.graph = None
        self._initialize_connection()

    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, TimeoutError),
        max_tries=5,
        max_time=30
    )
    def _initialize_connection(self) -> None:
        """Initialize Redis connection with exponential backoff retry logic"""
        try:
            logger.info(f"Attempting to connect to Redis at {self.redis_url}")
            
            # Parse the Redis URL
            parsed = urlparse(self.redis_url)
            
            # Extract host and port
            hostname = parsed.hostname or 'redis-graph'
            port = parsed.port or 6380
            
            # Extract username and password if present
            username = None
            password = None
            if '@' in parsed.netloc:
                auth = parsed.netloc.split('@')[0]
                if ':' in auth:
                    if '@' in auth:
                        username, password = auth.split(':')
                    else:
                        password = auth.split(':')[1]
            
            # Extract database number
            db = 0
            if parsed.path:
                try:
                    db = int(parsed.path.lstrip('/'))
                except ValueError:
                    pass
            
            # Parse query parameters
            query_params = parse_qs(parsed.query)
            
            self.redis_client = StrictRedis(
                host=hostname,
                port=port,
                db=db,
                username=username,
                password=password,
                decode_responses=True,
                socket_connect_timeout=int(os.getenv('REDIS_CONNECT_TIMEOUT', '5')),
                socket_timeout=int(os.getenv('REDIS_SOCKET_TIMEOUT', '5')),
                retry_on_timeout=True,
                health_check_interval=int(os.getenv('REDIS_HEALTH_CHECK_INTERVAL', '30'))
            )
            
            if not self._test_connection():
                raise ConnectionError(f"Could not connect to Redis at {self.redis_url}")

            self.graph = Graph(
                os.getenv('REDIS_GRAPH_NAME', 'reco_graph'),
                self.redis_client
            )
            logger.info(f"Successfully connected to Redis at {self.redis_url}")
            
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Redis connection error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while connecting to Redis: {str(e)}")
            raise

    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, TimeoutError),
        max_tries=3
    )
    def _test_connection(self) -> bool:
        """Test Redis connection with retries"""
        try:
            return self.redis_client.ping()
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Failed to ping Redis at {self.redis_url}: {str(e)}")
            return False

    def get_connection_info(self) -> dict:
        """Get current connection information"""
        if not self.redis_client:
            return {'status': 'disconnected'}
            
        conn_kwargs = self.redis_client.connection_pool.connection_kwargs
        return {
            'host': conn_kwargs.get('host', 'redis-graph'),
            'port': conn_kwargs.get('port', 6380),
            'db': conn_kwargs.get('db', 0),
            'url': self.redis_url,
            'status': 'connected' if self._test_connection() else 'disconnected'
        }

    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, TimeoutError),
        max_tries=3
    )
    def ensure_connection(self) -> None:
        """Ensure Redis connection is alive with retries"""
        if not self.redis_client or not self._test_connection():
            logger.warning("Redis connection lost, attempting to reconnect...")
            self._initialize_connection()

    def query_graph(self, query: str, parameters: Optional[dict] = None) -> List[Any]:
        """Execute a graph query with connection check and retries"""
        self.ensure_connection()
        
        @backoff.on_exception(
            backoff.expo,
            (ConnectionError, TimeoutError),
            max_tries=3
        )
        def execute_query():
            try:
                # Make sure we're passing parameters correctly to redisgraph-py
                if parameters:
                    result = self.graph.query(query, parameters)
                else:
                    result = self.graph.query(query)
                return [record for record in result.result_set if record]
            except Exception as e:
                logger.error(f"Error executing RedisGraph query: {str(e)}")
                raise

        return execute_query()

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_tries=3
    )
    def get_author_openalex_id(self, orcid: str) -> tuple:
        """Fetch OpenAlex ID for an author using their ORCID with retries.""" 
        try:
            response = requests.get(
                f"{self.openalex_api_url}/authors",
                params={"filter": f"orcid:{orcid}"},
                timeout=10
            )
            response.raise_for_status()
            
            if response.json().get('results'):
                author_data = response.json()['results'][0]
                logger.info(f"Successfully fetched OpenAlex ID for ORCID: {orcid}")
                return author_data['id'], author_data.get('orcid')
            else:
                logger.warning(f"No OpenAlex author found with ORCID: {orcid}")
                raise ValueError(f"No OpenAlex author found with ORCID: {orcid}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching OpenAlex ID for ORCID {orcid}: {str(e)}")
            raise

    def create_expert_node(self, orcid: str, name: str):
        """Create or update an Expert node."""
        query = """
        MERGE (e:Expert {orcid: $orcid})
        SET e.name = $name
        """
        params = {'orcid': orcid, 'name': name}
        self.graph.query(query, params)
        logger.info(f"Expert node created or updated for ORCID: {orcid}")

    def create_domain_node(self, domain_id: str, name: str):
        """Create or update a Domain node."""
        query = """
        MERGE (d:Domain {id: $domain_id})
        SET d.name = $name
        """
        params = {'domain_id': domain_id, 'name': name}
        self.graph.query(query, params)
        logger.info(f"Domain node created or updated for domain ID: {domain_id}")

    def create_field_node(self, field_id: str, name: str):
        """Create or update a Field node."""
        query = """
        MERGE (f:Field {id: $field_id})
        SET f.name = $name
        """
        params = {'field_id': field_id, 'name': name}
        self.graph.query(query, params)
        logger.info(f"Field node created or updated for field ID: {field_id}")

    def create_subfield_node(self, subfield_id: str, name: str):
        """Create or update a Subfield node."""
        query = """
        MERGE (sf:Subfield {id: $subfield_id})
        SET sf.name = $name
        """
        params = {'subfield_id': subfield_id, 'name': name}
        self.graph.query(query, params)
        logger.info(f"Subfield node created or updated for subfield ID: {subfield_id}")

    def create_related_to_relationship(self, orcid: str, domain_id: str):
        """Create a RELATED_TO relationship between Expert and Domain."""
        query = """
        MATCH (e:Expert {orcid: $orcid})
        MATCH (d:Domain {id: $domain_id})
        MERGE (e)-[r:RELATED_TO]->(d)
        """
        params = {'orcid': orcid, 'domain_id': domain_id}
        self.graph.query(query, params)
        logger.info(f"RELATED_TO relationship created between Expert {orcid} and Domain {domain_id}")

    def get_graph_stats(self) -> Dict[str, int]:
        """
        Get statistics about the graph database.
        
        Returns:
            Dict containing counts of different node types and relationships
        """
        self.ensure_connection()
        
        try:
            # Count nodes by type
            expert_count = self.query_graph("MATCH (e:Expert) RETURN COUNT(e) as count")[0][0]
            domain_count = self.query_graph("MATCH (d:Domain) RETURN COUNT(d) as count")[0][0]
            field_count = self.query_graph("MATCH (f:Field) RETURN COUNT(f) as count")[0][0]
            subfield_count = self.query_graph("MATCH (sf:Subfield) RETURN COUNT(sf) as count")[0][0]

            # Count relationships
            related_to_count = self.query_graph("MATCH ()-[r:RELATED_TO]->() RETURN COUNT(r) as count")[0][0]

            return {
                'Expert Count': expert_count,
                'Domain Count': domain_count,
                'Field Count': field_count,
                'Subfield Count': subfield_count,
                'RELATED_TO Relationships': related_to_count
            }

        except Exception as e:
            logger.error(f"Error getting graph stats: {str(e)}")
            return {}

# Instantiate GraphDatabase class
graph_db = GraphDatabase()

