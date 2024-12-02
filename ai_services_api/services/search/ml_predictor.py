import logging
from typing import List, Dict, Optional, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class MLPredictor:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=10000
        )
        self.query_vectors = None
        self.queries = []

    def train(self, historical_queries: List[str]):
        """Train the predictor on historical queries"""
        try:
            self.queries = historical_queries
            self.query_vectors = self.vectorizer.fit_transform(historical_queries)
            logger.info(f"Trained on {len(historical_queries)} queries")
        except Exception as e:
            logger.error(f"Error training ML predictor: {e}")

    def predict(self, 
               partial_query: str, 
               context: Optional[Dict[str, Any]] = None,
               limit: int = 5) -> List[str]:
        """Predict queries based on partial input"""
        try:
            if not self.query_vectors or not self.queries:
                return []

            # Transform partial query
            partial_vector = self.vectorizer.transform([partial_query])

            # Calculate similarities
            similarities = cosine_similarity(partial_vector, self.query_vectors)
            
            # Get top matches
            top_indices = similarities[0].argsort()[-limit:][::-1]
            
            predictions = [
                query for idx, query in enumerate(self.queries)
                if idx in top_indices and query.lower().startswith(partial_query.lower())
            ]

            return predictions[:limit]

        except Exception as e:
            logger.error(f"Error in ML prediction: {e}")
            return []

    def update(self, new_query: str):
        """Update the model with a new query"""
        try:
            if new_query not in self.queries:
                self.queries.append(new_query)
                if len(self.queries) % 100 == 0:  # Retrain periodically
                    self.train(self.queries)
        except Exception as e:
            logger.error(f"Error updating ML predictor: {e}")