import os
import logging
import psycopg2
from urllib.parse import urlparse
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class GraphDatabaseInitializer:
    def __init__(self):
        # Initialize Neo4j connection
        self._neo4j_driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
            auth=(
                os.getenv('NEO4J_USER', 'neo4j'),
                os.getenv('NEO4J_PASSWORD')
            )
        )

    @staticmethod
    def get_db_connection():
        """Create a connection to PostgreSQL database."""
        # Check if we're running in Docker
        in_docker = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
        
        # Use DATABASE_URL if provided, else fallback to environment variables
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            parsed_url = urlparse(database_url)
            host = parsed_url.hostname
            port = parsed_url.port
            dbname = parsed_url.path[1:]
            user = parsed_url.username
            password = parsed_url.password
        else:
            host = 'postgres' if in_docker else 'localhost'
            port = '5432'
            dbname = os.getenv('POSTGRES_DB', 'aphrcdb')
            user = os.getenv('POSTGRES_USER', 'aphrcuser')
            password = os.getenv('POSTGRES_PASSWORD', 'kimu')

        try:
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
            )
            logger.info(f"Successfully connected to database: {dbname}")
            return conn
        except psycopg2.OperationalError as e:
            logger.error(f"Error connecting to the database: {e}")
            raise

    def _get_neo4j_session(self):
        """Create a Neo4j session"""
        return self._neo4j_driver.session()

    def _create_indexes(self):
        """Create indexes for performance optimization"""
        index_queries = [
            "CREATE INDEX expert_orcid IF NOT EXISTS FOR (e:Expert) ON (e.orcid)",
            "CREATE INDEX field_name IF NOT EXISTS FOR (f:Field) ON (f.name)",
            "CREATE INDEX subfield_name IF NOT EXISTS FOR (sf:Subfield) ON (sf.name)",
            "CREATE INDEX domain_name IF NOT EXISTS FOR (d:Domain) ON (d.name)"
        ]
        
        with self._get_neo4j_session() as session:
            for query in index_queries:
                try:
                    session.run(query)
                    logger.info(f"Index created: {query}")
                except Exception as e:
                    logger.warning(f"Error creating index: {e}")

    def _fetch_experts_data(self):
        """Fetch experts data from PostgreSQL"""
        conn = None
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT 
                    orcid, 
                    firstname, 
                    lastname, 
                    domains, 
                    fields, 
                    subfields 
                FROM experts
            """)
            
            experts_data = cur.fetchall()
            logger.info(f"Fetched {len(experts_data)} experts from database")
            return experts_data
        except Exception as e:
            logger.error(f"Error fetching experts data: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def create_expert_node(self, orcid, name):
        """Create or update an expert node"""
        with self._get_neo4j_session() as session:
            try:
                session.run(
                    "MERGE (e:Expert {orcid: $orcid}) "
                    "ON CREATE SET e.name = $name "
                    "ON MATCH SET e.name = $name", 
                    {"orcid": orcid, "name": name}
                )
            except Exception as e:
                logger.error(f"Error creating expert node: {e}")
                raise

    def create_domain_node(self, domain_name):
        """Create a domain node"""
        with self._get_neo4j_session() as session:
            try:
                session.run(
                    "MERGE (d:Domain {name: $name})", 
                    {"name": domain_name}
                )
            except Exception as e:
                logger.error(f"Error creating domain node: {e}")
                raise

    def create_field_node(self, field_name):
        """Create a field node"""
        with self._get_neo4j_session() as session:
            try:
                session.run(
                    "MERGE (f:Field {name: $name})", 
                    {"name": field_name}
                )
            except Exception as e:
                logger.error(f"Error creating field node: {e}")
                raise

    def create_subfield_node(self, subfield_name):
        """Create a subfield node"""
        with self._get_neo4j_session() as session:
            try:
                session.run(
                    "MERGE (sf:Subfield {name: $name})", 
                    {"name": subfield_name}
                )
            except Exception as e:
                logger.error(f"Error creating subfield node: {e}")
                raise

    def create_relationships(self, orcid, domains, fields, subfields):
        """Create relationships between expert and domain/field/subfield nodes"""
        with self._get_neo4j_session() as session:
            try:
                # Create relationships for unique domains, fields, and subfields
                for domain in set(domains or []):
                    session.run(
                        """
                        MATCH (e:Expert {orcid: $orcid})
                        MATCH (d:Domain {name: $domain})
                        MERGE (e)-[:WORKS_IN_DOMAIN]->(d)
                        """, 
                        {"orcid": orcid, "domain": domain}
                    )

                for field in set(fields or []):
                    session.run(
                        """
                        MATCH (e:Expert {orcid: $orcid})
                        MATCH (f:Field {name: $field})
                        MERGE (e)-[:WORKS_IN_FIELD]->(f)
                        """, 
                        {"orcid": orcid, "field": field}
                    )

                for subfield in set(subfields or []):
                    session.run(
                        """
                        MATCH (e:Expert {orcid: $orcid})
                        MATCH (sf:Subfield {name: $subfield})
                        MERGE (e)-[:WORKS_IN_SUBFIELD]->(sf)
                        """, 
                        {"orcid": orcid, "subfield": subfield}
                    )
            except Exception as e:
                logger.error(f"Error creating relationships: {e}")
                raise

    def initialize_graph(self):
        """Main method to initialize the graph database"""
        try:
            # Create indexes
            self._create_indexes()

            # Fetch experts data from PostgreSQL
            experts_data = self._fetch_experts_data()
            
            if not experts_data:
                logger.warning("No experts data found to process")
                return

            # Process each expert's data
            for expert_data in experts_data:
                try:
                    orcid, firstname, lastname, domains, fields, subfields = expert_data

                    if not orcid:
                        continue

                    # Create expert node
                    expert_name = f"{firstname} {lastname}"
                    self.create_expert_node(orcid, expert_name)

                    # Create domain, field, and subfield nodes
                    for domain in set(domains or []):
                        self.create_domain_node(domain)
                    
                    for field in set(fields or []):
                        self.create_field_node(field)
                    
                    for subfield in set(subfields or []):
                        self.create_subfield_node(subfield)

                    # Create relationships
                    self.create_relationships(orcid, domains, fields, subfields)
                    
                    logger.info(f"Processed expert: {expert_name}")

                except Exception as e:
                    logger.error(f"Error processing expert data: {e}")
                    continue

            logger.info("Graph initialization complete!")

        except Exception as e:
            logger.error(f"Graph initialization failed: {e}")
            raise

    def close(self):
        """Close the Neo4j driver connection"""
        if self._neo4j_driver:
            self._neo4j_driver.close()


def main():
    # Initialize the graph database
    initializer = GraphDatabaseInitializer()
    try:
        # Run the graph initialization
        initializer.initialize_graph()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        raise
    finally:
        initializer.close()

if __name__ == "__main__":
    main()