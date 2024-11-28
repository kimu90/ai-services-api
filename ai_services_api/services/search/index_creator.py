import os
import psycopg2
import numpy as np
import faiss
import pickle
import logging
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()

class IndexCreator:
    def __init__(self):
        # Define base paths
        self.base_dir = Path(os.getenv('BASE_DIR', '/code'))
        self.models_dir = self.base_dir / 'models' / 'search'
        
        # Ensure directories exist
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Define file paths
        self.index_path = self.models_dir / 'faiss_index.idx'
        self.mapping_path = self.models_dir / 'chunk_mapping.pkl'

        # Initialize the embedding model
        self.model = SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'))

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

    def fetch_data_from_db(self):
        """Fetch data from the PostgreSQL database."""
        conn = self.get_db_connection()
        try:
            cur = conn.cursor()

            query = """
            SELECT 
                p.doi,
                p.title,
                p.abstract,
                p.summary,
                string_agg(DISTINCT t.tag_name, ' | ') as tags,
                string_agg(DISTINCT a.name, ' | ') as authors
            FROM publications p
            LEFT JOIN publication_tag pt ON pt.publication_doi = p.doi
            LEFT JOIN tags t ON t.tag_id = pt.tag_id
            LEFT JOIN author_publication ap ON ap.doi = p.doi
            LEFT JOIN authors a ON a.author_id = ap.author_id
            GROUP BY p.doi, p.title, p.abstract, p.summary;
            """

            cur.execute(query)
            rows = cur.fetchall()

            data = []
            for row in rows:
                publication = {
                    'doi': row[0] or '',
                    'title': row[1] or '',
                    'abstract': row[2] or '',
                    'summary': row[3] or '',
                    'tags': row[4] or '',
                    'authors': row[5] or ''
                }
                data.append(publication)

            logger.info(f"Fetched {len(data)} publications from the database")
            return data
        except Exception as e:
            logger.error(f"Error fetching data from database: {e}")
            return []
        finally:
            cur.close()
            conn.close()

    def create_faiss_index(self, data):
        """Create FAISS index and save it along with the chunk mapping."""
        try:
            if not data:
                logger.error("No data provided for index creation")
                return False

            # Prepare text data
            texts = [
                f"Title: {item['title']}\nAbstract: {item['abstract']}\nSummary: {item['summary']}\nTags: {item['tags']}\nAuthors: {item['authors']}"
                for item in data
            ]
            
            # Generate embeddings
            logger.info("Generating embeddings...")
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
            
            if embeddings.shape[0] == 0:
                logger.error("No embeddings generated")
                return False

            logger.info(f"Generated embeddings shape: {embeddings.shape}")

            # Create and save FAISS index
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            
            try:
                index.add(embeddings.astype(np.float32))
                faiss.write_index(index, str(self.index_path))
                logger.info(f"FAISS index saved at: {self.index_path}")
            except Exception as e:
                logger.error(f"Error saving FAISS index: {e}")
                return False
            
            # Create and save chunk mapping
            chunk_mapping = {i: item for i, item in enumerate(data)}
            with open(self.mapping_path, 'wb') as f:
                pickle.dump(chunk_mapping, f)
            logger.info(f"Chunk mapping saved at: {self.mapping_path}")
            
            return True

        except Exception as e:
            logger.error(f"Error in index creation: {e}")
            return False

def main():
    try:
        # Create index creator instance
        creator = IndexCreator()
        
        # Fetch data
        logger.info("Fetching data from database...")
        data = creator.fetch_data_from_db()
        
        if not data:
            logger.error("No data fetched from database")
            exit(1)
            
        # Create index
        logger.info("Creating FAISS index...")
        if creator.create_faiss_index(data):
            logger.info("Search index created successfully!")
        else:
            logger.error("Failed to create search index")
            exit(1)
            
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        exit(1)

if __name__ == "__main__":
    main()