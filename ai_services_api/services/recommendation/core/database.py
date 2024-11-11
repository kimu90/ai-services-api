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

# Load environment variables from .env file
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
            
            # Parse Redis URL
            url_parts = redis.connection.URL.from_url(self.redis_url)
            
            self.redis_client = StrictRedis(
                host=url_parts.hostname,
                port=url_parts.port or 6380,
                db=url_parts.database or 0,
                password=url_parts.password,
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

    def query_graph(self, query: str, params: Optional[dict] = None) -> List[Any]:
        """Execute a graph query with connection check and retries"""
        self.ensure_connection()
        
        @backoff.on_exception(
            backoff.expo,
            (ConnectionError, TimeoutError),
            max_tries=3
        )
        def execute_query():
            try:
                result = self.graph.query(query, params) if params else self.graph.query(query)
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

    def get_author_works_by_openalex_id(self, openalex_id: str):
        """Fetch works for an author using their OpenAlex ID and extract domain, field, and subfield information."""
        try:
            response = requests.get(f"{self.openalex_api_url}/works", params={"filter": f"authorships.author.id:{openalex_id}"})
            if response.status_code == 200:
                works = response.json().get('results', [])
                topics_info = []
                for work in works:
                    for topic in work.get('topics', []):
                        domain = topic.get('domain')
                        field = topic.get('field')
                        subfield = topic.get('subfield')
                        
                        # Append the topic information if at least one of domain, field, or subfield is present
                        if domain or field or subfield:
                            topics_info.append({
                                'domain': self.extract_domain_info(domain) if domain else None,
                                'field': self.extract_field_info(field) if field else None,
                                'subfield': self.extract_subfield_info(subfield) if subfield else None
                            })
                logger.info(f"Successfully fetched works for OpenAlex ID: {openalex_id}")
                return topics_info
            else:
                logger.warning(f"No works found for OpenAlex author ID: {openalex_id}")
                raise ValueError(f"No works found for OpenAlex author ID: {openalex_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching works for OpenAlex ID {openalex_id}: {e}")
            raise

    def extract_domain_info(self, domain):
        """Extract domain details from the domain object."""
        return {
            'id': domain['id'],
            'display_name': domain['display_name']
        }

    def extract_field_info(self, field):
        """Extract field details from the field object."""
        return {
            'id': field['id'],
            'display_name': field['display_name']
        }

    def extract_subfield_info(self, subfield):
        """Extract subfield details from the subfield object."""
        return {
            'id': subfield['id'],
            'display_name': subfield['display_name']
        }

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

    def create_related_to_field_relationship(self, orcid: str, field_id: str):
        """Create a RELATED_TO relationship between Expert and Field."""
        query = """
        MATCH (e:Expert {orcid: $orcid})
        MATCH (f:Field {id: $field_id})
        MERGE (e)-[r:RELATED_TO]->(f)
        """
        params = {'orcid': orcid, 'field_id': field_id}
        self.graph.query(query, params)
        logger.info(f"RELATED_TO relationship created between Expert {orcid} and Field {field_id}")

    def create_related_to_subfield_relationship(self, orcid: str, subfield_id: str):
        """Create a RELATED_TO relationship between Expert and Subfield."""
        query = """
        MATCH (e:Expert {orcid: $orcid})
        MATCH (sf:Subfield {id: $subfield_id})
        MERGE (e)-[r:RELATED_TO]->(sf)
        """
        params = {'orcid': orcid, 'subfield_id': subfield_id}
        self.graph.query(query, params)
        logger.info(f"RELATED_TO relationship created between Expert {orcid} and Subfield {subfield_id}")
