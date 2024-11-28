import os
import logging
import argparse
import asyncio
from dotenv import load_dotenv
from ai_services_api.services.data.database_setup import create_database_if_not_exists, create_tables, drop_all_tables
from ai_services_api.services.data.openalex_processor import OpenAlexProcessor
from ai_services_api.services.recommendation.graph_initializer import GraphDatabaseInitializer
from ai_services_api.services.search.index_creator import IndexCreator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Ensure all required environment variables are set."""
    load_dotenv()
    
    required_vars = [
        'DATABASE_URL',
        'GEMINI_API_KEY',
        'NEO4J_URI',
        'NEO4J_USER',
        'NEO4J_PASSWORD',
        'MODEL_PATH'  
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def initialize_database(args):
    """Initialize or reset the PostgreSQL database."""
    try:
        # Create database if it doesn't exist
        logger.info("Ensuring database exists...")
        create_database_if_not_exists()
        
        if args.reset:
            logger.info("Dropping all existing tables...")
            drop_all_tables()
        
        logger.info("Creating database tables...")
        create_tables()
        logger.info("Database initialization complete!")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def process_data(args):
    """Process both publications and experts data."""
    processor = OpenAlexProcessor()
    try:
        logger.info("Loading publications from OpenAlex...")
        processor.process_works(max_publications=args.publications)
        logger.info("Publication loading complete!")

        # Process experts from CSV
        logger.info("Processing experts from CSV...")
        await processor.process_experts("sme.csv")
        logger.info("Expert processing complete!")
        
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        raise
    finally:
        processor.close()

def initialize_graph():
    """Initialize the Neo4j graph database."""
    graph_initializer = GraphDatabaseInitializer()
    try:
        logger.info("Initializing graph database...")
        graph_initializer.initialize_graph()
        logger.info("Graph initialization complete!")
    except Exception as e:
        logger.error(f"Graph initialization failed: {e}")
        raise
    finally:
        graph_initializer.close()

def create_search_index():
    """Create FAISS search index."""
    index_creator = IndexCreator()
    try:
        logger.info("Fetching data for search index creation...")
        data = index_creator.fetch_data_from_db()
        
        if not data:
            logger.error("No data available for index creation")
            return False
            
        logger.info("Creating FAISS index...")
        success = index_creator.create_faiss_index(data)
        
        if success:
            logger.info("Search index creation complete!")
            return True
        else:
            logger.error("Failed to create search index")
            return False
    except Exception as e:
        logger.error(f"Search index creation failed: {e}")
        return False

async def main():
    parser = argparse.ArgumentParser(description='Initialize and populate the APHRC database system.')
    parser.add_argument('--reset', action='store_true', help='Reset the database before initialization')
    parser.add_argument('--publications', type=int, default=10, help='Number of publications to load')
    parser.add_argument('--skip-experts', action='store_true', help='Skip processing experts data')
    parser.add_argument('--skip-graph', action='store_true', help='Skip graph database initialization')
    parser.add_argument('--skip-search', action='store_true', help='Skip search index creation')
    args = parser.parse_args()

    try:
        setup_environment()
        initialize_database(args)
        
        # Process both publications and experts
        await process_data(args)

        if not args.skip_graph:
            initialize_graph()

        if not args.skip_search:
            if not create_search_index():
                logger.error("Search index creation failed")
                raise RuntimeError("Search index creation failed")

        logger.info("System initialization completed successfully!")

    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())