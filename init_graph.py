import asyncio
import logging
import time
from ai_services_api.services.recommendation.scripts.initial_data_loader import DataLoader
from ai_services_api.services.recommendation.core.database import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

        # Prepare data directly from the provided data
        data = [
    # Name, ORCID, Domain, Field, Subfields
    ("Fengbo Zhao", "https://orcid.org/0000-0002-1023-8974", "Health Sciences", "Medicine", 
        ["Cardiology and Cardiovascular Medicine", "Interventional Cardiology", "Pediatric Cardiology", "Heart Failure", "Arrhythmia"]),
    ("Manne Andersson", "https://orcid.org/0000-0002-2013-9574", "Health Sciences", "Medicine", 
        ["Surgery", "General Surgery", "Pediatric Surgery", "Cardiology and Cardiovascular Medicine", "Arrhythmia"]),
    ("Janina Behrens", "https://orcid.org/0000-0002-9723-8087", "Health Sciences", "Medicine", 
        ["Pathology and Forensic Medicine", "Histopathology", "Neuropathology", "Cardiology and Cardiovascular Medicine"]),
    ("Xiaoxin Shi", "https://orcid.org/0000-0003-0739-7189", "Health Sciences", "Medicine", 
        ["Physiology", "Cell Physiology", "Neurophysiology", "Pediatric Cardiology", "Arrhythmia"]),
    ("Charlie Davis", "https://orcid.org/0000-0003-4743-8985", "Health Sciences", "Medicine", 
        ["Otorhinolaryngology", "ENT Surgery", "Sleep Medicine", "Pediatric Surgery", "Interventional Cardiology"]),
    ("David Clark", "https://orcid.org/0000-0002-8795-0134", "Health Sciences", "Medicine", 
        ["Epidemiology", "Infectious Diseases", "Environmental Epidemiology", "Pathology and Forensic Medicine"]),
    ("Eve Martinez", "https://orcid.org/0000-0002-4855-9095", "Health Sciences", "Medicine", 
        ["Pulmonary and Respiratory Medicine", "Pulmonary Rehabilitation", "Sleep Medicine", "Epidemiology", "Pediatric Cardiology"]),
    ("Frank Moore", "https://orcid.org/0000-0002-8795-0134", "Life Sciences", "Agricultural and Biological Sciences", 
        ["Food Science", "Food Technology", "Nutrition Science", "Plant Science", "Aquatic Science"]),
    ("Grace Lee", "https://orcid.org/0000-0003-4743-8985", "Life Sciences", "Agricultural and Biological Sciences", 
        ["General Agricultural and Biological Sciences", "Agronomy", "Animal Science", "Plant Science", "Food Science"]),
    ("Hannah Wright", "https://orcid.org/0000-0002-3417-7926", "Life Sciences", "Agricultural and Biological Sciences", 
        ["Plant Science", "Plant Pathology", "Crop Science", "Food Science", "Nutrition Science"]),
    ("Isaac Harris", "https://orcid.org/0000-0002-3041-6336", "Life Sciences", "Agricultural and Biological Sciences", 
        ["Aquatic Science", "Marine Biology", "Fisheries Science", "Food Technology", "Plant Pathology"]),
    ("Jack Walker", "https://orcid.org/0000-0002-8523-3385", "Physical Sciences", "Engineering", 
        ["Electrical and Electronic Engineering", "Power Engineering", "Telecommunications", "Biomedical Engineering"]),
    ("Kathy Robinson", "https://orcid.org/0000-0003-1083-1126", "Physical Sciences", "Engineering", 
        ["Automotive Engineering", "Mechanical Engineering", "Systems Engineering", "Biomedical Engineering", "Ocean Engineering"]),
    ("Liam Young", "https://orcid.org/0000-0002-4170-5715", "Physical Sciences", "Engineering", 
        ["Ocean Engineering", "Offshore Engineering", "Coastal Engineering", "Mechanical Engineering", "Automotive Engineering"]),
    ("Mona Scott", "https://orcid.org/0000-0000-0098-0000", "Physical Sciences", "Engineering", 
        ["Biomedical Engineering", "Bioengineering", "Neuroengineering", "Ocean Engineering", "Coastal Engineering"]),
    ("Nina Lewis", "https://orcid.org/0000-0002-9723-8087", "Physical Sciences", "Engineering", 
        ["Mechanics of Materials", "Materials Science", "Structural Engineering", "Biomedical Engineering", "Telecommunications"])
]
        logger.info(f"Starting data loading process with {len(data)} records")

        # Process and load nodes and edges into the graph
        await data_loader.load_data(data)

        # Verify the graph after loading
        logger.info("Verifying graph data...")
        stats = data_loader.verify_graph()

        logger.info("Data loading completed successfully")
        logger.info("Graph Statistics:")
        for key, value in stats.items():
            logger.info(f"{key}: {value}")

    except Exception as e:
        logger.error(f"Error during data loading: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Data loading process interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
