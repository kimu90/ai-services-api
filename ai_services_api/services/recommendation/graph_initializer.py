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
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            parsed_url = urlparse(database_url)
            host = parsed_url.hostname
            port = parsed_url.port
            dbname = parsed_url.path[1:]
            user = parsed_url.username
            password = parsed_url.password
        else:
            host = os.getenv('POSTGRES_HOST', 'localhost')
            port = os.getenv('POSTGRES_PORT', '5432')
            dbname = os.getenv('POSTGRES_DB', 'aphrc')
            user = os.getenv('POSTGRES_USER', 'postgres')
            password = os.getenv('POSTGRES_PASSWORD', 'p0stgres')

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
        """Create necessary indexes in Neo4j"""
        index_queries = [
            "CREATE INDEX expert_id IF NOT EXISTS FOR (e:Expert) ON (e.id)",
            "CREATE INDEX domain_name IF NOT EXISTS FOR (d:Domain) ON (d.name)",
            "CREATE INDEX field_name IF NOT EXISTS FOR (f:Field) ON (f.name)",
            "CREATE INDEX subfield_name IF NOT EXISTS FOR (sf:Subfield) ON (sf.name)",
            "CREATE INDEX expertise_name IF NOT EXISTS FOR (ex:Expertise) ON (ex.name)"
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
                    id,
                    firstname, 
                    lastname,
                    knowledge_expertise,
                    domains, 
                    fields, 
                    subfields
                FROM experts_expert
                WHERE id IS NOT NULL
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

    def create_expert_node(self, session, expert_id, name):
        """Create or update an expert node"""
        try:
            session.run(
                """
                MERGE (e:Expert {id: $id}) 
                SET e.name = $name
                """, 
                {"id": str(expert_id), "name": name}
            )
        except Exception as e:
            logger.error(f"Error creating expert node: {e}")
            raise

    def create_domain_relationships(self, session, expert_id, domains):
        """Create domain nodes and relationships"""
        if not domains:
            return
            
        for domain in domains:
            try:
                session.run(
                    """
                    MATCH (e:Expert {id: $expert_id})
                    MERGE (d:Domain {name: $domain})
                    MERGE (e)-[:WORKS_IN_DOMAIN]->(d)
                    """,
                    {"expert_id": str(expert_id), "domain": domain}
                )
            except Exception as e:
                logger.error(f"Error creating domain relationship: {e}")

    def create_field_relationships(self, session, expert_id, fields):
        """Create field nodes and relationships"""
        if not fields:
            return
            
        for field in fields:
            try:
                session.run(
                    """
                    MATCH (e:Expert {id: $expert_id})
                    MERGE (f:Field {name: $field})
                    MERGE (e)-[:WORKS_IN_FIELD]->(f)
                    """,
                    {"expert_id": str(expert_id), "field": field}
                )
            except Exception as e:
                logger.error(f"Error creating field relationship: {e}")

    def create_subfield_relationships(self, session, expert_id, subfields):
        """Create subfield nodes and relationships"""
        if not subfields:
            return
            
        for subfield in subfields:
            try:
                session.run(
                    """
                    MATCH (e:Expert {id: $expert_id})
                    MERGE (sf:Subfield {name: $subfield})
                    MERGE (e)-[:WORKS_IN_SUBFIELD]->(sf)
                    """,
                    {"expert_id": str(expert_id), "subfield": subfield}
                )
            except Exception as e:
                logger.error(f"Error creating subfield relationship: {e}")

    def create_expertise_relationships(self, session, expert_id, expertise_list):
        """Create expertise nodes and relationships"""
        if not expertise_list:
            return
            
        for expertise in expertise_list:
            try:
                session.run(
                    """
                    MATCH (e:Expert {id: $expert_id})
                    MERGE (ex:Expertise {name: $expertise})
                    MERGE (e)-[:HAS_EXPERTISE]->(ex)
                    """,
                    {"expert_id": str(expert_id), "expertise": expertise}
                )
            except Exception as e:
                logger.error(f"Error creating expertise relationship: {e}")

    def initialize_graph(self):
        """Initialize the graph with experts and their relationships"""
        try:
            # Create indexes first
            self._create_indexes()
            
            # Fetch experts data
            experts_data = self._fetch_experts_data()
            
            if not experts_data:
                logger.warning("No experts data found to process")
                return

            # Process each expert
            with self._get_neo4j_session() as session:
                for expert_data in experts_data:
                    try:
                        # Unpack data
                        (expert_id, firstname, lastname, knowledge_expertise, 
                         domains, fields, subfields) = expert_data

                        if not expert_id:
                            continue

                        # Create expert node
                        expert_name = f"{firstname} {lastname}"
                        self.create_expert_node(session, expert_id, expert_name)

                        # Create relationships for each category
                        self.create_domain_relationships(session, expert_id, domains)
                        self.create_field_relationships(session, expert_id, fields)
                        self.create_subfield_relationships(session, expert_id, subfields)
                        self.create_expertise_relationships(session, expert_id, knowledge_expertise)

                        logger.info(f"Processed expert: {expert_name}")

                    except Exception as e:
                        logger.error(f"Error processing expert data: {e}")
                        continue

            logger.info("Graph initialization complete!")

        except Exception as e:
            logger.error(f"Graph initialization failed: {e}")
            raise

    def close(self):
        """Close the Neo4j driver"""
        if self._neo4j_driver:
            self._neo4j_driver.close()

def main():
    initializer = GraphDatabaseInitializer()
    try:
        initializer.initialize_graph()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        raise
    finally:
        initializer.close()

if __name__ == "__main__":
    main()