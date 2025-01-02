import os
import logging
import asyncio
from datetime import datetime
from typing import Optional

from ai_services_api.services.data.database_setup import (
    create_database_if_not_exists,
    create_tables,
    fix_experts_table,
)
from ai_services_api.services.data.openalex.openalex_processor import OpenAlexProcessor
from ai_services_api.services.data.openalex.publication_processor import PublicationProcessor
from ai_services_api.services.data.openalex.ai_summarizer import TextSummarizer
from ai_services_api.services.recommendation.graph_initializer import GraphDatabaseInitializer
from ai_services_api.services.search.index_creator import ExpertSearchIndexManager
from ai_services_api.services.search.redis_index_manager import ExpertRedisIndexManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def run_monthly_setup():
    """Execute monthly data processing tasks."""
    try:
        logger.info("Starting monthly setup process")
        
        # Initialize database
        logger.info("Ensuring database exists...")
        create_database_if_not_exists()
        
        logger.info("Fixing experts table...")
        fix_experts_table()
        
        logger.info("Creating database tables...")
        create_tables()

        # Process OpenAlex data
        processor = OpenAlexProcessor()
        try:
            logger.info("Updating experts with OpenAlex data...")
            await processor.update_experts_with_openalex()
            logger.info("Expert data enrichment complete!")

            # Process publications
            logger.info("Processing publications data...")
            summarizer = TextSummarizer()
            pub_processor = PublicationProcessor(processor.db, summarizer)
            await processor.process_publications(pub_processor, source='openalex')
            
        finally:
            processor.close()

        # Initialize graph database
        logger.info("Initializing graph database...")
        graph_initializer = GraphDatabaseInitializer()
        if not graph_initializer.initialize_graph():
            raise Exception("Graph initialization failed")

        # Create search indices
        logger.info("Creating search indices...")
        index_creator = ExpertSearchIndexManager()
        if not index_creator.create_faiss_index():
            raise Exception("FAISS index creation failed")

        redis_creator = ExpertRedisIndexManager()
        if not redis_creator.create_redis_index():
            raise Exception("Redis index creation failed")

        logger.info("Monthly setup completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Monthly setup failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_monthly_setup())
