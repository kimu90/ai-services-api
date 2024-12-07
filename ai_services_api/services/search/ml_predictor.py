import logging
from typing import List, Dict, Optional, Any
import numpy as np
from collections import defaultdict
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MLPredictor:
    def __init__(self):
        # Prefix tree for fast prefix matching
        self.prefix_tree = {}
        # Frequency dictionary for each query
        self.query_freq = defaultdict(int)
        # Recent queries with timestamps
        self.recent_queries = []
        # Maximum number of recent queries to store
        self.max_recent = 1000
        # Time window for recent queries (in hours)
        self.time_window = 24
        
    def _add_to_prefix_tree(self, query: str):
        """Add a query to the prefix tree"""
        current = self.prefix_tree
        query = query.lower()
        for char in query:
            if char not in current:
                current[char] = {}
            current = current[char]
        if '_end_' not in current:
            current['_end_'] = set()
        current['_end_'].add(query)

    def _get_from_prefix_tree(self, prefix: str, limit: int) -> List[str]:
        """Get all queries starting with prefix"""
        current = self.prefix_tree
        prefix = prefix.lower()
        
        # Navigate to prefix node
        for char in prefix:
            if char not in current:
                return []
            current = current[char]
            
        # Collect all complete words from this point
        results = []
        def collect_words(node, limit):
            if '_end_' in node:
                results.extend(node['_end_'])
            if len(results) >= limit:
                return
            for char in node:
                if char != '_end_':
                    collect_words(node[char], limit)
                    
        collect_words(current, limit)
        return results[:limit]

    def train(self, historical_queries: List[str]):
        """Train the predictor on historical queries"""
        try:
            # Reset data structures
            self.prefix_tree = {}
            self.query_freq.clear()
            
            # Process each query
            for query in historical_queries:
                query = query.strip()
                if not query:
                    continue
                    
                self._add_to_prefix_tree(query)
                self.query_freq[query.lower()] += 1
                
            logger.info(f"Trained on {len(historical_queries)} queries")
            
        except Exception as e:
            logger.error(f"Error training ML predictor: {e}")

    def predict(self, 
               partial_query: str,
               context: Optional[Dict[str, Any]] = None,
               limit: int = 5) -> List[str]:
        """Predict queries based on partial input"""
        try:
            if not partial_query or len(partial_query) < 2:
                return []
                
            # Get matching queries from prefix tree
            matches = self._get_from_prefix_tree(partial_query, limit * 2)
            
            # Score matches
            scored_matches = []
            current_time = datetime.now()
            
            for query in matches:
                score = 0
                
                # Frequency score (0-5)
                freq = self.query_freq[query.lower()]
                score += min(freq / 10, 5)
                
                # Recency score (0-3)
                recent_count = sum(1 for rq in self.recent_queries 
                                 if rq['query'].lower() == query.lower() 
                                 and current_time - rq['timestamp'] < timedelta(hours=self.time_window))
                score += min(recent_count, 3)
                
                # Length similarity score (0-2)
                length_diff = abs(len(query) - len(partial_query))
                score += max(0, 2 - (length_diff * 0.1))
                
                # Context score if available (0-2)
                if context and 'user_queries' in context:
                    user_query_count = sum(1 for uq in context['user_queries'] 
                                         if uq.lower() == query.lower())
                    score += min(user_query_count * 0.5, 2)
                
                scored_matches.append((query, score))
            
            # Sort by score and return top matches
            scored_matches.sort(key=lambda x: x[1], reverse=True)
            return [query for query, _ in scored_matches[:limit]]
            
        except Exception as e:
            logger.error(f"Error in ML prediction: {e}")
            return []
            
    def update(self, new_query: str):
        """Update the model with a new query"""
        try:
            new_query = new_query.strip()
            if not new_query:
                return
                
            # Update prefix tree and frequency
            self._add_to_prefix_tree(new_query)
            self.query_freq[new_query.lower()] += 1
            
            # Update recent queries
            self.recent_queries.append({
                'query': new_query,
                'timestamp': datetime.now()
            })
            
            # Maintain recent queries limit
            if len(self.recent_queries) > self.max_recent:
                self.recent_queries = self.recent_queries[-self.max_recent:]
                
        except Exception as e:
            logger.error(f"Error updating ML predictor: {e}")