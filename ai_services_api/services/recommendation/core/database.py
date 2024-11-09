import logging
import redis
from redisgraph import Graph
import requests
from ai_services_api.services.recommendation.config import get_settings
from redis import StrictRedis, ConnectionError, TimeoutError
from typing import Optional, List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential



# Set up logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

class GraphDatabase:
    def __init__(self, max_retries: int = 3):
        """
        Initialize Redis connection with retry logic
        
        Args:
            max_retries: Maximum number of connection attempts
        """
        self.max_retries = max_retries
        self._initialize_connection()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def _initialize_connection(self):
        """Initialize Redis connection with retry logic"""
        try:
            self.redis_client = StrictRedis(
                host='redis',  # Try localhost first
                port=6379,        # Default Redis port
                db=0,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            if not self._test_connection():
                # If localhost fails, try redis-graph
                self.redis_client = StrictRedis(
                    host='redis-graph',
                    port=6380,        # Try default port
                    db=0,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                
                if not self._test_connection():
                    raise ConnectionError("Could not connect to Redis on any configured host")

            self.graph = Graph('reco_graph', self.redis_client)
            logger.info("Successfully connected to Redis and initialized RedisGraph")
            
        except ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while connecting to Redis: {e}")
            raise

    def _test_connection(self) -> bool:
        """Test Redis connection"""
        try:
            return self.redis_client.ping()
        except (ConnectionError, TimeoutError):
            return False

    def get_connection_info(self) -> dict:
        """Get current connection information"""
        return {
            'host': self.redis_client.connection_pool.connection_kwargs['host'],
            'port': self.redis_client.connection_pool.connection_kwargs['port'],
            'db': self.redis_client.connection_pool.connection_kwargs['db']
        }

    def ensure_connection(self):
        """Ensure Redis connection is alive"""
        try:
            if not self._test_connection():
                logger.warning("Redis connection lost, attempting to reconnect...")
                self._initialize_connection()
        except Exception as e:
            logger.error(f"Error ensuring Redis connection: {e}")
            raise

    def query_graph(self, query: str, params: Optional[dict] = None):
        """Execute a graph query with connection check"""
        self.ensure_connection()  # Verify connection before query
        try:
            result = self.graph.query(query, params) if params else self.graph.query(query)
            return [record for record in result.result_set if record]
        except Exception as e:
            logger.error(f"Error executing RedisGraph query: {e}")
            raise

    def get_author_openalex_id(self, orcid: str):
        """Fetch OpenAlex ID for an author using their ORCID."""
        try:
            response = requests.get(f"{self.openalex_api_url}/authors", params={"filter": f"orcid:{orcid}"})
            if response.status_code == 200 and response.json().get('results'):
                author_data = response.json()['results'][0]
                logger.info(f"Successfully fetched OpenAlex ID for ORCID: {orcid}")
                return author_data['id'], author_data['orcid']
            else:
                logger.warning(f"No OpenAlex author found with ORCID: {orcid}")
                raise ValueError(f"No OpenAlex author found with ORCID: {orcid}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching OpenAlex ID for ORCID {orcid}: {e}")
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

    def add_expert(self, orcid: str, name: str):
        """Add an expert and related topics to the graph."""
        try:
            # Create or update Expert node
            self.create_expert_node(orcid, name)

            # Fetch OpenAlex ID and Works
            openalex_id, _ = self.get_author_openalex_id(orcid)
            topics_info = self.get_author_works_by_openalex_id(openalex_id)

            # Create or update Domain, Field, and Subfield nodes, and relationships
            for topic in topics_info:
                if topic['domain']:
                    self.create_domain_node(topic['domain']['id'], topic['domain']['display_name'])
                    self.create_related_to_relationship(orcid, topic['domain']['id'])
                if topic['field']:
                    self.create_field_node(topic['field']['id'], topic['field']['display_name'])
                    self.create_related_to_field_relationship(orcid, topic['field']['id'])
                if topic['subfield']:
                    self.create_subfield_node(topic['subfield']['id'], topic['subfield']['display_name'])
                    self.create_related_to_subfield_relationship(orcid, topic['subfield']['id'])

        except Exception as e:
            logger.error(f"Error adding expert {orcid}: {e}")
            raise
