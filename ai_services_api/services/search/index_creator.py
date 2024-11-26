import psycopg2
import numpy as np
import faiss
import pickle
import logging
from pathlib import Path
from urllib.parse import urlparse
from ai_services_api.services.search.config import get_settings
from ai_services_api.services.search.embedding_model import EmbeddingModel
import os
from dotenv import load_dotenv

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
        self.base_dir = Path('/code')
        self.services_dir = self.base_dir / 'ai_services_api/services'
        self.search_dir = self.services_dir / 'search'
        self.models_dir = self.search_dir / 'models'
        
        # Ensure all directories exist
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Define file paths
        self.index_path = self.models_dir / 'faiss_index.idx'
        self.mapping_path = self.models_dir / 'chunk_mapping.pkl'

    @staticmethod
    def get_db_connection():
        """
        Create a connection to PostgreSQL database using the DATABASE_URL environment variable.
        """
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
            logger.info(f"Successfully connected to database: {dbname}")
            return conn
        except psycopg2.OperationalError as e:
            logger.error(f"Error connecting to the database: {e}")
            raise

    def fetch_data_from_db(self):
        """Fetch data from the PostgreSQL database."""
        conn = IndexCreator.get_db_connection()
        try:
            cur = conn.cursor()

            query = """
            SELECT p.doi, p.title, p.abstract, p.summary, t.tag_name, a.name AS author_name
            FROM publications p
            LEFT JOIN publication_tag pt ON pt.publication_doi = p.doi
            LEFT JOIN tags t ON t.tag_id = pt.tag_id
            LEFT JOIN author_publication ap ON ap.doi = p.doi
            LEFT JOIN authors a ON a.author_id = ap.author_id;
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
                    'author': row[5] or ''
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

    def create_faiss_index(self, data=None, model_path=None):
        """Create FAISS index and save it along with the chunk mapping."""
        try:
            settings = get_settings()
            model_path = model_path or settings.MODEL_PATH
            
            embedding_model = EmbeddingModel(model_path)

            # Validate expected embedding dimension
            test_embedding = embedding_model.get_embedding("Test text")
            if test_embedding is None or test_embedding.size == 0:
                logger.error("Failed to get test embedding")
                return False
            
            expected_dimension = len(test_embedding[0])
            logger.info(f"Expected embedding dimension: {expected_dimension}")

            # Prepare text data
            texts = [
                f"{item.get('title', '')} {item.get('abstract', '')} {item.get('summary', '')} {item.get('tags', '')} {item.get('author', '')}"
                for item in data
            ]
            
            embeddings = []
            valid_data = []

            for text, item in zip(texts, data):
                try:
                    embedding_result = embedding_model.get_embedding(text)
                    
                    if embedding_result is not None and len(embedding_result) > 0:
                        # Ensure single embedding and convert to numpy array
                        embedding = embedding_result[0] if isinstance(embedding_result[0], (list, np.ndarray)) else embedding_result
                        embedding = np.asarray(embedding, dtype=np.float32)
                        
                        if embedding.ndim != 1:
                            logger.warning(f"Invalid embedding shape for text: {text}")
                        else:
                            embeddings.append(embedding)
                            valid_data.append(item)
                    else:
                        logger.warning(f"Invalid embedding for text: {text}")
                except Exception as e:
                    logger.error(f"Error processing text: {text}, Error: {e}")

            # Ensure embeddings is a 2D numpy array
            if not embeddings:
                logger.error("No valid embeddings generated")
                return False

            embeddings = np.array(embeddings, dtype=np.float32)
            
            if embeddings.ndim != 2:
                logger.error(f"Invalid embedding shape: {embeddings.shape}")
                return False

            logger.info(f"Generated embeddings: {embeddings.shape}")

            # Create FAISS index
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            
            # Explicitly convert to float32 and handle potential issues
            try:
                index.add(embeddings)
            except Exception as e:
                logger.error(f"Error adding embeddings to FAISS index: {e}")
                return False
            
            # Save FAISS index
            faiss.write_index(index, str(self.index_path))
            
            # Create and save chunk mapping
            chunk_mapping = {i: item for i, item in enumerate(valid_data)}
            with open(self.mapping_path, 'wb') as f:
                pickle.dump(chunk_mapping, f)
                
            logger.info(f"FAISS index saved at: {self.index_path}")
            logger.info(f"Chunk mapping saved at: {self.mapping_path}")
            
            return True

        except Exception as e:
            logger.error(f"Comprehensive error in index creation: {e}")
            return False

if __name__ == "__main__":
    # Create an instance of IndexCreator
    index_creator = IndexCreator()

    # Fetch data from the database
    data = index_creator.fetch_data_from_db()
    if not data:
        logger.error("No data fetched from the database.")
        exit(1)

    # Create FAISS index
    success = index_creator.create_faiss_index(data)
    
    if success:
        logger.info("FAISS index created successfully")
    else:
        logger.error("Failed to create FAISS index")
        exit(1)
