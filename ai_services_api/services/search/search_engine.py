import faiss
import pickle
import os
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from ai_services_api.services.search.embedding_model import EmbeddingModel
from ai_services_api.services.search.cache_manager import CacheManager
from ai_services_api.services.search.database_manager import DatabaseManager
from ai_services_api.services.search.ml_predictor import MLPredictor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class SearchEngine:
    def __init__(self):
        try:
            logger.info("Initializing Production SearchEngine...")
            self._init_components()
            self._load_models()
            logger.info("Production SearchEngine initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing SearchEngine: {e}")
            raise

    def _init_components(self):
        try:
            # Initialize core components
            self.db = DatabaseManager()
            self.cache = CacheManager()
            self.embedding_model = EmbeddingModel()
            self.ml_predictor = MLPredictor()
            
            # Initialize query tracking
            self.query_history = self.db.get_recent_queries(limit=1000)
            self.term_frequencies = self.db.get_term_frequencies()
            
            # Set scoring weights
            self.weights = {
                'term_frequency': 0.3,
                'temporal_relevance': 0.2,
                'semantic_similarity': 0.3,
                'user_preference': 0.2
            }
            
            self.temporal_decay_rate = 0.1
            self.max_history_age = 30  # days
            
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            raise

    def _load_models(self):
        try:
            current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            models_dir = current_dir.parent / 'models'
            
            # Load FAISS index
            self.index_path = models_dir / 'faiss_index.idx'
            if not os.path.isfile(self.index_path):
                raise FileNotFoundError(f"FAISS index not found at {self.index_path}")
            self.index = faiss.read_index(str(self.index_path))
            
            # Load document mappings
            self.mapping_path = models_dir / 'chunk_mapping.pkl'
            if not os.path.isfile(self.mapping_path):
                raise FileNotFoundError(f"Chunk mapping not found at {self.mapping_path}")
            with open(self.mapping_path, 'rb') as f:
                self.chunk_mapping = pickle.load(f)
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            raise

    def search(self, query: str, k: int = 5, user_id: Optional[str] = None) -> List[Dict]:
        try:
            logger.info(f"Searching for: {query}")
            
            # Check cache first
            cache_key = f"search_{query}_{k}_{user_id}"
            cached_result = self.cache.get(cache_key)
            if cached_result:
                return cached_result
            
            # Update query history
            self._update_query_history(query, user_id)
            
            # Generate query embedding
            query_vector = self.embedding_model.get_embedding(query)
            
            # Search FAISS index
            num_candidates = min(k * 2, self.index.ntotal)
            distances, indices = self.index.search(query_vector, num_candidates)
            
            # Process results
            results = self._process_results(indices[0], distances[0])
            
            # Apply personalization
            if user_id:
                results = self._personalize_results(results, user_id)
            
            # Cache results
            final_results = results[:k]
            self.cache.set(cache_key, final_results, expire=300)
            
            logger.info(f"Found {len(final_results)} results")
            return final_results
            
        except Exception as e:
            logger.error(f"Error during search: {e}")
            raise

    def predict_queries(self, 
                   partial_query: str, 
                   limit: int = 5, 
                   context: Optional[Dict[str, Any]] = None) -> List[str]:
        try:
            if not partial_query or len(partial_query) < 2:
                return []

            # Check cache with shorter expiration for predictions
            cache_key = f"pred_{partial_query}_{limit}_{context.get('user_id', '')}"
            cached_result = self.cache.get(cache_key)
            if cached_result:
                return cached_result

            predictions = set()
            
            # Get predictions from ML predictor first (fast)
            ml_predictions = self.ml_predictor.predict(
                partial_query, 
                context,
                limit=limit
            )
            predictions.update(ml_predictions)

            # If we don't have enough predictions, get from database
            if len(predictions) < limit:
                db_predictions = self.db.get_matching_queries(
                    partial_query, 
                    limit=limit - len(predictions)
                )
                predictions.update(db_predictions)

            # Convert to list and limit results
            results = list(predictions)[:limit]
            
            # Cache results for a short time
            self.cache.set(cache_key, results, expire=60)  # Cache for 1 minute

            return results

        except Exception as e:
            logger.error(f"Error predicting queries: {e}")
            return []

    def _calculate_prediction_score(self, 
                                 prediction: str, 
                                 partial_query: str,
                                 user_id: Optional[str],
                                 query_embedding: np.ndarray) -> float:
        try:
            # Term frequency score
            term_freq_score = sum(self.term_frequencies.get(term, 0) 
                                for term in prediction.lower().split())
            term_freq_score = min(term_freq_score / 100, 1.0)

            # Temporal relevance
            temporal_score = self._calculate_temporal_relevance(prediction)

            # Semantic similarity
            pred_embedding = self.embedding_model.get_embedding(prediction)
            semantic_score = float(np.dot(query_embedding, pred_embedding.T))
            semantic_score = (semantic_score + 1) / 2

            # User preference score
            user_score = 0.0
            if user_id:
                user_score = self._calculate_user_preference_score(prediction, user_id)

            # Combine scores
            final_score = (
                self.weights['term_frequency'] * term_freq_score +
                self.weights['temporal_relevance'] * temporal_score +
                self.weights['semantic_similarity'] * semantic_score +
                self.weights['user_preference'] * user_score
            )

            return final_score

        except Exception as e:
            logger.error(f"Error calculating prediction score: {e}")
            return 0.0

    def _calculate_temporal_relevance(self, query: str) -> float:
        try:
            recent_queries = self.db.get_query_timestamps(query, limit=10)
            if not recent_queries:
                return 0.0

            current_time = datetime.utcnow()
            scores = []
            
            for timestamp in recent_queries:
                age = (current_time - timestamp).total_seconds()
                max_age = self.max_history_age * 24 * 3600
                if age <= max_age:
                    scores.append(np.exp(-self.temporal_decay_rate * age / max_age))

            return max(scores) if scores else 0.0

        except Exception as e:
            logger.error(f"Error calculating temporal relevance: {e}")
            return 0.0

    def _process_results(self, indices: np.ndarray, distances: np.ndarray) -> List[Dict]:
        results = []
        for idx, (distance, doc_idx) in enumerate(zip(distances, indices)):
            if doc_idx < 0 or doc_idx >= len(self.chunk_mapping):
                continue

            try:
                metadata = self.chunk_mapping[doc_idx]
                max_distance = 100
                similarity = max(0, 1 - (distance / max_distance))
                
                result = {
                    'metadata': metadata,
                    'similarity_score': float(similarity)
                }
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing result {idx}: {e}")
                continue

        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results

    def _personalize_results(self, results: List[Dict], user_id: str) -> List[Dict]:
        try:
            user_prefs = self.db.get_user_preferences(user_id)
            if not user_prefs:
                return results

            for result in results:
                if 'tags' in result['metadata']:
                    tags = set(t.strip() for t in result['metadata']['tags'].split('|'))
                    pref_boost = sum(user_prefs.get(tag, 0) for tag in tags) / len(tags)
                    result['similarity_score'] *= (1 + pref_boost)

            results.sort(key=lambda x: x['similarity_score'], reverse=True)
            return results
        except Exception as e:
            logger.error(f"Error in personalization: {e}")
            return results

    def _update_query_history(self, query: str, user_id: Optional[str] = None):
        try:
            # Update database
            self.db.add_query(query, user_id)
            
            # Update local cache
            self.query_history.append({
                'query': query,
                'timestamp': datetime.utcnow(),
                'user_id': user_id
            })
            
            # Update term frequencies
            terms = query.lower().split()
            for term in terms:
                self.term_frequencies[term] = self.term_frequencies.get(term, 0) + 1
                
        except Exception as e:
            logger.error(f"Error updating query history: {e}")

    def _get_user_predictions(self, user_id: str, partial_query: str) -> List[str]:
        try:
            user_queries = self.db.get_user_queries(user_id, limit=100)
            return [q for q in user_queries if q.lower().startswith(partial_query.lower())]
        except Exception as e:
            logger.error(f"Error getting user predictions: {e}")
            return []

    def update_user_preferences(self, user_id: str, relevant_docs: List[str]):
        try:
            self.db.update_user_preferences(user_id, relevant_docs)
            logger.info(f"Updated preferences for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")