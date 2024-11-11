import asyncio
import logging
from pathlib import Path
import sys
import time
from ai_services_api.services.recommendation.scripts.initial_data_loader import DataLoader
from ai_services_api.services.recommendation.core.database import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def read_orcids(file_path: Path) -> list:
    """
    Read ORCID IDs from a single-column CSV file.
    Returns a list of valid ORCID IDs.
    """
    orcids = []
    try:
        with open(file_path, 'r') as f:
            # Skip header
            next(f)
            # Read remaining lines and strip any whitespace
            orcids = [line.strip() for line in f if line.strip()]
            
        logger.info(f"Successfully read {len(orcids)} ORCID IDs")
        # Log a few examples for verification
        if orcids:
            logger.info(f"First few ORCID IDs: {orcids[:3]}")
            
        return orcids
            
    except Exception as e:
        logger.error(f"Error reading ORCID IDs: {e}")
        raise

async def wait_for_services():
    """Wait for Redis and Redis Graph to be ready"""
    db = GraphDatabase()
    max_retries = 30
    retry_interval = 2

    for i in range(max_retries):
        try:
            if db._test_connection():
                logger.info("Successfully connected to Redis services")
                return True
        except Exception as e:
            logger.warning(f"Attempt {i + 1}/{max_retries} to connect to Redis services failed: {e}")
        
        logger.info(f"Waiting {retry_interval} seconds before next retry...")
        time.sleep(retry_interval)
    
    raise ConnectionError("Could not connect to Redis services after maximum retries")

async def main():
    try:
        # Wait for Redis services to be ready
        logger.info("Checking Redis services connection...")
        await wait_for_services()
        
        # Initialize the DataLoader
        data_loader = DataLoader()
        
        # Define the path to your CSV file
        csv_path = Path('/code/try_test.csv')
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found at: {csv_path}")
        
        # Read ORCID IDs
        logger.info(f"Reading ORCID IDs from {csv_path}")
        orcids = await read_orcids(csv_path)
        
        if not orcids:
            raise ValueError("No valid ORCID IDs found in the file")
            
        logger.info(f"Starting data loading process with {len(orcids)} ORCID IDs")
        
        # Now pass the list of ORCIDs to the modified load_initial_experts method
        await data_loader.load_initial_experts(orcids)
        
        # Verify the graph after loading
        logger.info("Verifying graph data...")
        stats = data_loader.verify_graph()
        
        logger.info("Data loading completed successfully")
        logger.info("Graph Statistics:")
        for key, value in stats.items():
            logger.info(f"{key}: {value}")
            
    except Exception as e:
        logger.error(f"Error during data loading: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Data loading process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)