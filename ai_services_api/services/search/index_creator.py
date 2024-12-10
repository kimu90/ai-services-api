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
from typing import List, Dict, Any, Optional
from src.utils.db_utils import DatabaseConnector

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ExpertSearchIndexManager:
    def __init__(self):
        """Initialize ExpertSearchIndexManager."""
        self.setup_paths()
        self.setup_redis()
        self.model = SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'))
        self.db = DatabaseConnector()

    def setup_paths(self):
        """Setup paths for storing models and mappings."""
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.models_dir = current_dir / 'models'
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.models_dir / 'expert_faiss_index.idx'
        self.mapping_path = self.models_dir / 'expert_mapping.pkl'

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
        """Store expert embedding and metadata in Redis."""
        try:
            pipeline = self.redis_binary.pipeline()
            
            # Handle null values in metadata
            for key, value in metadata.items():
                if value is None:
                    metadata[key] = ''
            
            pipeline.hset(
                f"expert:{key}",
                mapping={
                    'vector': embedding.tobytes(),
                    'metadata': json.dumps(metadata)
                }
            )
            pipeline.execute()
        except Exception as e:
            logger.error(f"Error storing expert in Redis: {e}")

    def fetch_experts(self) -> List[Dict[str, Any]]:
        """Fetch all experts with retry logic."""
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                conn = self.db.get_connection()
                with conn.cursor() as cur:
                    # Check if table exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'experts_expert'
                        );
                    """)
                    if not cur.fetchone()[0]:
                        logger.warning("experts_expert table does not exist")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return []
                    
                    # Fetch expert data
                    cur.execute("""
                        SELECT 
                            id,
                            firstname,
                            lastname,
                            bio,
                            email,
                            knowledge_expertise,
                            fields,
                            subfields,
                            domains,
                            normalized_domains,
                            normalized_fields,
                            normalized_skills,
                            keywords,
                            orcid,
                            contact_details,
                            unit
                        FROM experts_expert
                        WHERE id IS NOT NULL
                    """)
                    rows = cur.fetchall()
                    
                    experts = []
                    for row in rows:
                        try:
                            expert = {
                                'id': row[0],
                                'name': f"{row[1]} {row[2]}",
                                'description': row[3] or '',
                                'email': row[4],
                                'specialties': {
                                    'expertise': row[5] if isinstance(row[5], str) else [],
                                    'fields': row[6] if isinstance(row[6], str) else [],
                                    'subfields': row[7] if isinstance(row[7], str) else [],
                                    'domains': row[8] if isinstance(row[8], str) else [],
                                    'normalized_domains': row[9] if isinstance(row[9], str) else [],
                                    'normalized_fields': row[10] if isinstance(row[10], str) else [],
                                    'normalized_skills': row[11] if isinstance(row[11], str) else [],
                                    'keywords': row[12] if isinstance(row[12], str) else []
                                },
                                'orcid': row[13],
                                'contact': row[14],
                                'unit': row[15]
                            }
                            experts.append(expert)
                        except Exception as e:
                            logger.error(f"Error processing expert data: {e}")
                    
                    return experts
                    
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

    def create_expert_text(self, expert: Dict[str, Any]) -> str:
        """Create searchable text from expert data."""
        specialties = expert['specialties']
        text_parts = [
            f"Name: {expert['name']}",
            f"Description: {expert['description']}",
            f"Unit: {expert['unit'] or ''}",
            f"Expertise: {' | '.join(specialties['expertise'])}",
            f"Fields: {' | '.join(specialties['fields'])}",
            f"Subfields: {' | '.join(specialties['subfields'])}",
            f"Domains: {' | '.join(specialties['domains'])}",
            f"Technical Skills: {' | '.join(specialties['normalized_skills'])}",
            f"Research Areas: {' | '.join(specialties['normalized_fields'])}",
            f"Primary Domains: {' | '.join(specialties['normalized_domains'])}",
            f"Keywords: {' | '.join(specialties['keywords'])}"
        ]
        return '\n'.join(text_parts)

    def create_faiss_index(self) -> bool:
        """Create FAISS index for expert search."""
        try:
            # Fetch expert data
            experts = self.fetch_experts()
            if not experts:
                logger.warning("No expert data available to create index")
                return False

            # Prepare text for embeddings
            texts = [self.create_expert_text(expert) for expert in experts]

            # Generate embeddings
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
            
            # Create and populate FAISS index
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            
            # Store embeddings and metadata
            for i, (expert, embedding) in enumerate(zip(experts, embeddings)):
                # Store in Redis
                self.store_in_redis(
                    str(expert['id']),
                    embedding,
                    {
                        'id': expert['id'],
                        'name': expert['name'],
                        'description': expert['description'],
                        'specialties': expert['specialties']
                    }
                )
                
                # Add to FAISS index
                index.add(embedding.reshape(1, -1).astype(np.float32))

            # Save FAISS index and mapping
            faiss.write_index(index, str(self.index_path))
            with open(self.mapping_path, 'wb') as f:
                pickle.dump({i: expert['id'] for i, expert in enumerate(experts)}, f)

            logger.info(f"Successfully created index with {len(experts)} experts")
            return True

        except Exception as e:
            logger.error(f"Error creating FAISS index: {e}")
            return False

    def search_experts(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar experts using the index.
        
        Args:
            query (str): Search query
            k (int): Number of results to return
            
        Returns:
            List of expert matches with metadata
        """
        try:
            # Load index and mapping
            index = faiss.read_index(str(self.index_path))
            with open(self.mapping_path, 'rb') as f:
                id_mapping = pickle.load(f)

            # Generate query embedding
            query_embedding = self.model.encode([query], convert_to_numpy=True)
            
            # Search index
            distances, indices = index.search(query_embedding.astype(np.float32), k)
            
            # Fetch results from Redis
            results = []
            for i, idx in enumerate(indices[0]):
                if idx < 0:  # FAISS may return -1 for not enough matches
                    continue
                    
                expert_id = id_mapping[idx]
                expert_data = self.redis_binary.hgetall(f"expert:{expert_id}")
                
                if expert_data:
                    metadata = json.loads(expert_data[b'metadata'].decode())
                    metadata['score'] = float(1 / (1 + distances[0][i]))  # Convert distance to similarity score
                    results.append(metadata)
            
            return results

        except Exception as e:
            logger.error(f"Error searching experts: {e}")
            return []

def initialize_expert_search():
    """Initialize expert search index."""
    try:
        manager = ExpertSearchIndexManager()
        return manager.create_faiss_index()
    except Exception as e:
        logger.error(f"Error initializing expert search: {e}")
        return False

if __name__ == "__main__":
    initialize_expert_search()