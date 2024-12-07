import os
import numpy as np
import faiss
import pickle
import redis
import json
import time
import logging
from pathlib import Path
from sentence_transformers import SentenceTransformer
from src.utils.db_utils import DatabaseConnector

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class SearchIndexManager:
    def __init__(self):
        """Initialize SearchIndexManager."""
        self.setup_paths()
        self.setup_redis()
        self.model = SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'))
        self.db = DatabaseConnector()

    def setup_paths(self):
        """Setup paths for storing models and mappings."""
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.models_dir = current_dir / 'models'
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.models_dir / 'faiss_index.idx'
        self.mapping_path = self.models_dir / 'chunk_mapping.pkl'

    def setup_redis(self):
        """Setup Redis connections."""
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_EMBEDDINGS_DB', 1)),
            decode_responses=True
        )
        self.redis_binary = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_EMBEDDINGS_DB', 1)),
            decode_responses=False
        )

    def store_in_redis(self, key: str, embedding: np.ndarray, metadata: dict):
        """Store embedding and metadata in Redis."""
        try:
            pipeline = self.redis_binary.pipeline()
            pipeline.hset(
                f"emb:{key}",
                mapping={
                    'vector': embedding.tobytes(),
                    'metadata': json.dumps(metadata)
                }
            )
            pipeline.execute()
        except Exception as e:
            logger.error(f"Error storing in Redis: {e}")

    def fetch_resources_and_experts(self):
        """Fetch resources and experts with retry logic."""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                conn = self.db.get_connection()
                with conn.cursor() as cur:
                    # First check if table exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'resources_resource'
                        );
                    """)
                    if not cur.fetchone()[0]:
                        logger.warning("resources_resource table does not exist yet")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return []
                    
                    # If table exists, fetch data
                    cur.execute("""
                        SELECT 
                            r.doi,
                            r.title,
                            r.abstract,
                            r.summary,
                            r.authors,
                            r.description,
                            e.firstname,
                            e.lastname,
                            e.knowledge_expertise,
                            e.fields,
                            e.subfields,
                            e.domains
                        FROM resources_resource r
                        LEFT JOIN experts_expert e ON e.id = r.expert_id
                        WHERE r.doi IS NOT NULL 
                        AND r.title IS NOT NULL
                    """)
                    rows = cur.fetchall()
                    
                    return [{
                        'doi': row[0],
                        'title': row[1],
                        'abstract': row[2],
                        'summary': row[3],
                        'authors': row[4],
                        'description': row[5],
                        'expert_name': f"{row[6]} {row[7]}" if row[6] and row[7] else None,
                        'knowledge_expertise': row[8] if row[8] else [],
                        'fields': row[9] if row[9] else [],
                        'subfields': row[10] if row[10] else [],
                        'domains': row[11] if row[11] else []
                    } for row in rows]
                    
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error("All retry attempts failed")
                    return []
            finally:
                if 'conn' in locals():
                    conn.close()

    def create_faiss_index(self):
        """Create FAISS index."""
        try:
            data = self.fetch_resources_and_experts()
            if not data:
                logger.warning("No data available to create index")
                return False

            # Prepare text for embeddings
            texts = [
                f"""Title: {item['title']}
                Abstract: {item['abstract'] or ''}
                Summary: {item['summary'] or ''}
                Description: {item['description'] or ''}
                Authors: {item['authors'] or ''}
                Expert: {item['expert_name'] or ''}
                Expertise: {' | '.join(item['knowledge_expertise'])}
                Fields: {' | '.join(item['fields'])}
                Subfields: {' | '.join(item['subfields'])}
                Domains: {' | '.join(item['domains'])}"""
                for item in data
            ]

            # Generate embeddings
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
            
            # Store in Redis and create FAISS index
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            
            for i, (item, embedding) in enumerate(zip(data, embeddings)):
                # Store in Redis
                self.store_in_redis(
                    f"res:{item['doi']}",
                    embedding,
                    {
                        'doi': item['doi'],
                        'title': item['title'],
                        'authors': item['authors'],
                        'expert_name': item['expert_name'],
                        'fields': item['fields'],
                        'domains': item['domains']
                    }
                )
                
                # Add to FAISS index
                index.add(embedding.reshape(1, -1).astype(np.float32))

            # Save FAISS index and mapping
            faiss.write_index(index, str(self.index_path))
            with open(self.mapping_path, 'wb') as f:
                pickle.dump({i: item['doi'] for i, item in enumerate(data)}, f)

            return True

        except Exception as e:
            logger.error(f"Error creating FAISS index: {e}")
            return False

def initialize_search():
    """Initialize search index."""
    try:
        manager = SearchIndexManager()
        return manager.create_faiss_index()
    except Exception as e:
        logger.error(f"Error initializing search: {e}")
        return False

if __name__ == "__main__":
    initialize_search()