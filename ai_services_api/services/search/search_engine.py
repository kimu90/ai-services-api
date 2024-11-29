import faiss
import pickle
import os
import logging
from pathlib import Path
from typing import List, Dict
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class EmbeddingModel:
    def __init__(self):
        try:
            logger.info("Initializing embedding model...")
            self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            logger.info("Embedding model initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing embedding model: {e}")
            raise

    def get_embedding(self, text: str) -> List[float]:
        try:
            embeddings = self.model.encode([text], convert_to_numpy=True)
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

class SearchEngine:
    def __init__(self):
        try:
            logger.info("Initializing SearchEngine...")
            self.embedding_model = EmbeddingModel()
            
            current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            models_dir = current_dir.parent / 'models'
            self.index_path = models_dir / 'faiss_index.idx'
            self.mapping_path = models_dir / 'chunk_mapping.pkl'
            
            if not os.path.isfile(self.index_path):
                raise FileNotFoundError(f"FAISS index not found at {self.index_path}")
            
            if not os.path.isfile(self.mapping_path):
                raise FileNotFoundError(f"Chunk mapping not found at {self.mapping_path}")
            
            logger.info("Loading FAISS index...")
            self.index = faiss.read_index(str(self.index_path))
            
            logger.info("Loading chunk mapping...")
            with open(self.mapping_path, 'rb') as f:
                self.chunk_mapping = pickle.load(f)
                
            logger.info(f"SearchEngine initialized with {len(self.chunk_mapping)} documents")
            
        except Exception as e:
            logger.error(f"Error initializing SearchEngine: {e}")
            raise

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Perform semantic search on the indexed documents.
        
        Args:
            query (str): The search query
            k (int): Number of results to return
            
        Returns:
            List[Dict]: List of search results with metadata and similarity scores
        """
        try:
            logger.info(f"Searching for: {query}")
            
            # Generate query embedding
            query_vector = self.embedding_model.get_embedding(query)
            
            # Perform search
            distances, indices = self.index.search(query_vector, k)
            
            # Format results
            results = []
            for idx, (distance, doc_idx) in enumerate(zip(distances[0], indices[0])):
                # Skip invalid indices
                if doc_idx < 0 or doc_idx >= len(self.chunk_mapping):
                    logger.warning(f"Invalid index {doc_idx} found in search results")
                    continue
                    
                try:
                    # Convert distance to similarity score (optional)
                    # FAISS returns L2 distance, smaller is better
                    # Converting to a similarity score between 0 and 1
                    max_distance = 100  # You may need to adjust this based on your embeddings
                    similarity = max(0, 1 - (distance / max_distance))
                    
                    result = {
                        'metadata': self.chunk_mapping[doc_idx],
                        'similarity_score': float(similarity)
                    }
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing result {idx}: {e}")
                    continue
            
            logger.info(f"Found {len(results)} valid results")
            return results
            
        except Exception as e:
            logger.error(f"Error during search: {e}")
            raise