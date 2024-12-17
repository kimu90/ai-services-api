import os
import logging
import psycopg2
from urllib.parse import urlparse
from neo4j import GraphDatabase
from dotenv import load_dotenv
import google.generativeai as genai
from typing import List, Dict, Any
import json


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

class GraphDatabaseInitializer:
    def __init__(self):
        """Initialize GraphDatabaseInitializer."""
        # Initialize Neo4j connection
        self._neo4j_driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
            auth=(
                os.getenv('NEO4J_USER', 'neo4j'),
                os.getenv('NEO4J_PASSWORD')
            )
        )

        # Initialize Gemini
        try:
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            self.model = genai.GenerativeModel('gemini-pro')
            logger.info("Gemini model initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Gemini model: {e}")
            # Set a flag to indicate Gemini is not available
            self.model = None

    def _normalize_expertise(self, expertise_list: List[str]) -> Dict[str, Any]:
        """Use Gemini to normalize and categorize expertise"""
        if not expertise_list:
            return {
                "primary_domains": [],
                "specific_fields": [],
                "technical_skills": []
            }

        # If Gemini is not available, use fallback categorization
        if self.model is None:
            return {
                "primary_domains": expertise_list[:2] if len(expertise_list) >= 2 else expertise_list,
                "specific_fields": expertise_list[2:4] if len(expertise_list) >= 4 else [],
                "technical_skills": expertise_list[4:] if len(expertise_list) >= 5 else []
            }

        prompt = f"""
        Analyze these areas of expertise and categorize them into the following structure.
        Expertise: {', '.join(expertise_list)}

        Return only the JSON structure below with these exact keys, nothing else:
        {{
            "primary_domains": [],
            "specific_fields": [],
            "technical_skills": []
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON if it's embedded in the response
            if '{\n' in response_text or '{' in response_text:
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    try:
                        categories = json.loads(json_str)
                        # Validate required keys
                        required_keys = {"primary_domains", "specific_fields", "technical_skills"}
                        if all(key in categories for key in required_keys):
                            return categories
                    except json.JSONDecodeError:
                        logger.error("Failed to parse Gemini response as JSON")
            
            # Fallback categorization if parsing fails
            return {
                "primary_domains": expertise_list[:2] if len(expertise_list) >= 2 else expertise_list,
                "specific_fields": expertise_list[2:4] if len(expertise_list) >= 4 else [],
                "technical_skills": expertise_list[4:] if len(expertise_list) >= 5 else []
            }

        except Exception as e:
            logger.error(f"Error using Gemini model: {str(e)}")
            # Return a basic categorization as fallback
            return {
                "primary_domains": expertise_list[:2] if len(expertise_list) >= 2 else expertise_list,
                "specific_fields": expertise_list[2:4] if len(expertise_list) >= 4 else [],
                "technical_skills": expertise_list[4:] if len(expertise_list) >= 5 else []
            }

    @staticmethod
    def get_db_connection():
        """Create a connection to PostgreSQL database."""
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            parsed_url = urlparse(database_url)
            conn_params = {
                'host': parsed_url.hostname,
                'port': parsed_url.port,
                'dbname': parsed_url.path[1:],
                'user': parsed_url.username,
                'password': parsed_url.password
            }
        else:
            conn_params = {
                'host': os.getenv('POSTGRES_HOST', 'localhost'),
                'port': os.getenv('POSTGRES_PORT', '5432'),
                'dbname': os.getenv('POSTGRES_DB', 'aphrc'),
                'user': os.getenv('POSTGRES_USER', 'postgres'),
                'password': os.getenv('POSTGRES_PASSWORD', 'p0stgres')
            }

        try:
            conn = psycopg2.connect(**conn_params)
            logger.info(f"Successfully connected to database: {conn_params['dbname']}")
            return conn
        except psycopg2.OperationalError as e:
            logger.error(f"Error connecting to the database: {e}")
            raise

    def _create_indexes(self):
        """Create necessary indexes in Neo4j"""
        index_queries = [
            "CREATE INDEX expert_id IF NOT EXISTS FOR (e:Expert) ON (e.id)",
            "CREATE INDEX domain_name IF NOT EXISTS FOR (d:Domain) ON (d.name)",
            "CREATE INDEX field_name IF NOT EXISTS FOR (f:Field) ON (f.name)",
            "CREATE INDEX expertise_name IF NOT EXISTS FOR (ex:Expertise) ON (ex.name)",
            "CREATE INDEX skill_name IF NOT EXISTS FOR (s:Skill) ON (s.name)"
        ]
        
        with self._neo4j_driver.session() as session:
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
                    first_name, 
                    last_name,
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

    def create_expert_node(self, session, expert_id: str, name: str, expertise_categories: Dict[str, List[str]]):
        """Create or update an expert node with categorized expertise"""
        try:
            # Validate expertise categories
            required_keys = {"primary_domains", "specific_fields", "technical_skills"}
            if not all(key in expertise_categories for key in required_keys):
                logger.warning(f"Missing required categories for expert {name}. Using empty lists for missing categories.")
                expertise_categories = {
                    "primary_domains": expertise_categories.get("primary_domains", []),
                    "specific_fields": expertise_categories.get("specific_fields", []),
                    "technical_skills": expertise_categories.get("technical_skills", [])
                }

            # Create expert node
            session.run(
                """
                MERGE (e:Expert {id: $id}) 
                SET e.name = $name
                """, 
                {"id": str(expert_id), "name": name}
            )

            # Create and connect expertise categories
            for domain in expertise_categories["primary_domains"]:
                if domain:  # Only create non-empty domains
                    session.run(
                        """
                        MATCH (e:Expert {id: $expert_id})
                        MERGE (d:Domain {name: $domain})
                        MERGE (e)-[:HAS_DOMAIN]->(d)
                        """,
                        {"expert_id": str(expert_id), "domain": domain}
                    )

            for field in expertise_categories["specific_fields"]:
                if field:  # Only create non-empty fields
                    session.run(
                        """
                        MATCH (e:Expert {id: $expert_id})
                        MERGE (f:Field {name: $field})
                        MERGE (e)-[:HAS_FIELD]->(f)
                        """,
                        {"expert_id": str(expert_id), "field": field}
                    )

            for skill in expertise_categories["technical_skills"]:
                if skill:  # Only create non-empty skills
                    session.run(
                        """
                        MATCH (e:Expert {id: $expert_id})
                        MERGE (s:Skill {name: $skill})
                        MERGE (e)-[:HAS_SKILL]->(s)
                        """,
                        {"expert_id": str(expert_id), "skill": skill}
                    )

            logger.info(f"Successfully created/updated expert node: {name}")

        except Exception as e:
            logger.error(f"Error creating expert node: {e}")
            raise

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
            with self._neo4j_driver.session() as session:
                for expert_data in experts_data:
                    try:
                        # Unpack data
                        (expert_id, first_name, last_name, knowledge_expertise, 
                         domains, fields, subfields) = expert_data

                        if not expert_id:
                            continue

                        # Normalize expertise using Gemini
                        expertise_categories = self._normalize_expertise(knowledge_expertise)

                        # Create expert node with categorized expertise
                        expert_name = f"{first_name} {last_name}"
                        self.create_expert_node(
                            session, 
                            expert_id, 
                            expert_name, 
                            expertise_categories
                        )

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