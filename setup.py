import os
import logging
import argparse
import asyncio
from dotenv import load_dotenv
from ai_services_api.services.data.database_setup import (
    create_database_if_not_exists, 
    create_tables,
    fix_experts_table,
    get_db_connection
)
from ai_services_api.services.data.openalex.openalex_processor import OpenAlexProcessor
from ai_services_api.services.data.openalex.publication_processor import PublicationProcessor
from ai_services_api.services.data.openalex.ai_summarizer import TextSummarizer
from ai_services_api.services.recommendation.graph_initializer import GraphDatabaseInitializer
from ai_services_api.services.search.index_creator import SearchIndexManager
from ai_services_api.services.search.redis_index_manager import RedisIndexManager

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
        'NEO4J_URI',
        'NEO4J_USER',
        'NEO4J_PASSWORD',
        'OPENALEX_API_URL',
        'GEMINI_API_KEY',
        'REDIS_URL'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def initialize_database(args):
    """Initialize the PostgreSQL database."""
    try:
        logger.info("Ensuring database exists...")
        create_database_if_not_exists()
        
        logger.info("Creating database tables...")
        create_tables()
        
        logger.info("Fixing experts table...")
        fix_experts_table()
        
        logger.info("Database initialization complete!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def initialize_graph():
    """Initialize the Neo4j graph database."""
    try:
        graph_initializer = GraphDatabaseInitializer()
        logger.info("Initializing graph database...")
        graph_initializer.initialize_graph()
        logger.info("Graph initialization complete!")
        return True
    except Exception as e:
        logger.error(f"Graph initialization failed: {e}")
        return False

async def process_data(args):
    """Process experts and publications data."""
    processor = OpenAlexProcessor()
    
    try:
        # Process expert data
        logger.info("Loading initial expert data...")
        await processor.load_initial_experts(args.expertise_csv)
        
        if not args.skip_openalex:
            logger.info("Updating experts with OpenAlex data...")
            await processor.update_experts_with_openalex()
            logger.info("Expert data enrichment complete!")
            
            # Initialize publication processing components
            if not args.skip_publications:
                logger.info("Processing publications data...")
                summarizer = TextSummarizer()
                pub_processor = PublicationProcessor(processor.db, summarizer)
                await processor.process_publications(pub_processor)
                logger.info("Publications processing complete!")
        
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        raise
    finally:
        processor.close()

def create_search_index():
    """Create FAISS search index."""
    index_creator = SearchIndexManager()
    try:
        logger.info("Creating FAISS search index...")
        success = index_creator.create_faiss_index()
        if success:
            logger.info("FAISS index creation complete!")
            return True
        else:
            logger.error("Failed to create FAISS index")
            return False
    except Exception as e:
        logger.error(f"FAISS index creation failed: {e}")
        return False

def create_redis_index():
    """Create Redis search index."""
    redis_creator = RedisIndexManager()
    try:
        logger.info("Creating Redis search index...")
        if redis_creator.clear_redis_indexes():
            success = redis_creator.create_redis_index()
            if success:
                logger.info("Redis index creation complete!")
                return True
        logger.error("Failed to create Redis index")
        return False
    except Exception as e:
        logger.error(f"Redis index creation failed: {e}")
        return False

async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Initialize and populate the research database.')
    parser.add_argument('--expertise-csv', type=str, default='expertise.csv',
                       help='Path to the expertise CSV file')
    parser.add_argument('--skip-openalex', action='store_true',
                       help='Skip OpenAlex data enrichment')
    parser.add_argument('--skip-publications', action='store_true',
                       help='Skip publications processing')
    parser.add_argument('--skip-graph', action='store_true',
                       help='Skip graph database initialization')
    parser.add_argument('--skip-search', action='store_true',
                       help='Skip search index creation')
    parser.add_argument('--skip-redis', action='store_true',
                       help='Skip Redis index creation')
    args = parser.parse_args()

    try:
        # Step 1: Setup environment
        setup_environment()
        
        # Step 2: Initialize database and ensure tables exist
        logger.info("Running database setup...")
        initialize_database(args)
        
        # Step 3: Process data (this should populate the tables)
        logger.info("Processing data...")
        await process_data(args)

        # Step 4: Verify tables are populated
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM resources_resource LIMIT 1
                );
            """)
            if not cur.fetchone()[0]:
                logger.warning("No data in resources_resource table. Search index may be empty.")
        finally:
            cur.close()
            conn.close()

        # Step 5: Initialize graph database (if not skipped)
        if not args.skip_graph:
            if not initialize_graph():
                logger.error("Graph initialization failed")
                raise RuntimeError("Graph initialization failed")

        # Step 6: Create search index (if not skipped and data exists)
        if not args.skip_search:
            if not create_search_index():
                logger.error("FAISS index creation failed")
                raise RuntimeError("FAISS index creation failed")

        # Step 7: Create Redis index (if not skipped)
        if not args.skip_redis:
            if not create_redis_index():
                logger.error("Redis index creation failed")
                raise RuntimeError("Redis index creation failed")

        logger.info("System initialization completed successfully!")

    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        raise

def run():
    """Entry point function."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import sys
    run()