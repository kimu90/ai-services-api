import os
import logging
import psycopg2
from urllib.parse import urlparse
from neo4j import GraphDatabase
import pandas as pd
import asyncio
from ai_services_api.services.recommendation.config import get_settings

class GraphDatabaseInitializer:
    def __init__(self):
        # Set up logging
        logging.basicConfig(level=logging.INFO, 
                            format='%(asctime)s - %(levelname)s - %(message)s')
        self._logger = logging.getLogger(__name__)

        # Initialize Neo4j connection
        settings = get_settings()
        self._neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    @staticmethod
    def get_db_connection():
        """Create a connection to PostgreSQL database using the DATABASE_URL environment variable."""
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set.")

        # Parse the database URL
        parsed_url = urlparse(database_url)
        host = parsed_url.hostname
        port = parsed_url.port
        dbname = parsed_url.path[1:]  # Removing the leading '/'
        user = parsed_url.username
        password = parsed_url.password

        try:
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
            )
            logging.info(f"Successfully connected to database: {dbname}")
            return conn
        except psycopg2.OperationalError as e:
            logging.error(f"Error connecting to the database: {e}")
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
                    self._logger.info(f"Index created: {query}")
                except Exception as e:
                    self._logger.warning(f"Error creating index: {e}")

    def _fetch_experts_data(self):
        """Fetch experts data from PostgreSQL"""
        conn = None
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            
            # Fetch all experts with their domains, fields, and subfields
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
            
            # Fetch all rows
            experts_data = cur.fetchall()
            
            return experts_data
        except Exception as e:
            self._logger.error(f"Error fetching experts data: {e}")
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
                self._logger.error(f"Error creating expert node: {e}")
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
                self._logger.error(f"Error creating domain node: {e}")
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
                self._logger.error(f"Error creating field node: {e}")
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
                self._logger.error(f"Error creating subfield node: {e}")
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
                self._logger.error(f"Error creating relationships: {e}")
                raise

    def initialize_graph(self):
        """Main method to initialize the graph database"""
        try:
            # Create indexes
            self._create_indexes()

            # Fetch experts data from PostgreSQL
            experts_data = self._fetch_experts_data()

            # Process each expert's data
            for expert_data in experts_data:
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

            self._logger.info("Graph initialization complete!")

        except Exception as e:
            self._logger.error(f"Graph initialization failed: {e}")

    def close(self):
        """Close the Neo4j driver connection"""
        if self._neo4j_driver:
            self._neo4j_driver.close()


def main():
    # Initialize the graph database
    graph_initializer = GraphDatabaseInitializer()
    try:
        # Run the graph initialization
        graph_initializer.initialize_graph()
    except Exception as e:
        logging.error(f"Initialization failed: {e}")
    finally:
        graph_initializer.close()

if __name__ == "__main__":
    main()