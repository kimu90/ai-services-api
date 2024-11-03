from typing import Dict, List, Union, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime

@dataclass
class WorkScore:
    work_id: str
    base_score: float
    topic_score: float
    citation_score: float
    collaborative_score: float
    recency_score: float
    final_score: float

class ScoreCalculator:
    """
    Enhanced scoring system for hybrid recommendations
    """
    
    def __init__(self):
        # Strategy weights
        self.weights = {
            'topic_based': 0.3,
            'citation_based': 0.4,
            'collaborative': 0.3
        }
        
        # Score normalization parameters
        self.max_citations = 1000  # Adjust based on your data
        self.max_topics_overlap = 10
        self.recency_weight = 0.1
        self.citation_decay = 0.95  # Citation score decay factor
        
    def normalize_score(self, score: float, max_value: float) -> float:
        """Normalize score to range [0,1]"""
        return min(1.0, score / max_value) if max_value > 0 else 0.0

    def calculate_recency_score(self, publication_year: int) -> float:
        """Calculate recency score based on publication year"""
        current_year = datetime.now().year
        years_old = current_year - publication_year
        return np.exp(-0.1 * years_old)  # Exponential decay

    def calculate_topic_similarity(
        self,
        base_topics: List[str],
        candidate_topics: List[str]
    ) -> float:
        """Calculate topic similarity score using Jaccard similarity"""
        if not base_topics or not candidate_topics:
            return 0.0
            
        base_set = set(base_topics)
        candidate_set = set(candidate_topics)
        
        intersection = len(base_set.intersection(candidate_set))
        union = len(base_set.union(candidate_set))
        
        return intersection / union if union > 0 else 0.0

    def calculate_citation_impact(
        self,
        citation_count: int,
        publication_year: int
    ) -> float:
        """Calculate citation impact score with time decay"""
        normalized_citations = self.normalize_score(citation_count, self.max_citations)
        years_old = datetime.now().year - publication_year
        time_decay = self.citation_decay ** years_old
        
        return normalized_citations * time_decay

    def calculate_hybrid_score(
        self,
        recommendations: Dict[str, List[Tuple[str, Dict[str, Union[str, int, float, List[str]]]]]],
        base_work: Dict[str, Union[str, int, float, List[str]]] = None
    ) -> List[WorkScore]:
        """
        Calculate hybrid recommendation scores with multiple factors
        
        Args:
            recommendations: Dictionary of recommendations from different strategies
                           Each recommendation includes work details
            base_work: Original work details for content-based comparison
            
        Returns:
            List of WorkScore objects sorted by final score
        """
        work_scores: Dict[str, WorkScore] = {}
        
        for strategy, works in recommendations.items():
            strategy_weight = self.weights.get(strategy, 0.2)
            
            for work_id, work_details in works:
                # Initialize work score if not exists
                if work_id not in work_scores:
                    work_scores[work_id] = WorkScore(
                        work_id=work_id,
                        base_score=0.0,
                        topic_score=0.0,
                        citation_score=0.0,
                        collaborative_score=0.0,
                        recency_score=0.0,
                        final_score=0.0
                    )
                
                # Calculate component scores
                citation_score = self.calculate_citation_impact(
                    work_details.get('citation_count', 0),
                    work_details.get('publication_year', datetime.now().year)
                )
                
                recency_score = self.calculate_recency_score(
                    work_details.get('publication_year', datetime.now().year)
                )
                
                topic_score = 0.0
                if base_work and 'topics' in work_details:
                    topic_score = self.calculate_topic_similarity(
                        base_work.get('topics', []),
                        work_details.get('topics', [])
                    )
                
                # Update scores based on strategy
                score = work_scores[work_id]
                if strategy == 'topic_based':
                    score.topic_score = topic_score
                elif strategy == 'citation_based':
                    score.citation_score = citation_score
                else:  # collaborative
                    score.collaborative_score = work_details.get('collaborative_score', 0.0)
                
                score.recency_score = recency_score
                
                # Calculate final score
                score.final_score = (
                    self.weights['topic_based'] * score.topic_score +
                    self.weights['citation_based'] * score.citation_score +
                    self.weights['collaborative'] * score.collaborative_score +
                    self.recency_weight * score.recency_score
                )
        
        # Sort by final score
        sorted_scores = sorted(
            work_scores.values(),
            key=lambda x: x.final_score,
            reverse=True
        )
        
        return sorted_scores

    def get_score_explanation(self, work_score: WorkScore) -> Dict[str, float]:
        """
        Get detailed explanation of score components
        """
        return {
            'topic_similarity': round(work_score.topic_score, 3),
            'citation_impact': round(work_score.citation_score, 3),
            'collaborative_signal': round(work_score.collaborative_score, 3),
            'recency_boost': round(work_score.recency_score, 3),
            'final_score': round(work_score.final_score, 3)
        }

# services/recommendation_service.py (updated to use enhanced ScoreCalculator)
class RecommendationService:
    def __init__(self):
        self.connector = GraphConnector()
        self.strategies = RecommendationStrategies(self.connector)
        self.enricher = DataEnricher(self.connector)
        self.score_calculator = ScoreCalculator()
        
    async def get_recommendations(
        self,
        author_id: Optional[str] = None,
        work_id: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        try:
            recommendations = {}
            base_work = None
            
            if author_id:
                collaborative_recs = self.strategies.get_collaborative_recommendations(
                    author_id, limit=limit
                )
                recommendations['collaborative'] = [
                    (rec[0], self._get_work_details(rec[0]))
                    for rec in collaborative_recs
                ]
            
            if work_id:
                base_work = self._get_work_details(work_id)
                content_recs = self.strategies.get_content_based_recommendations(
                    work_id, limit=limit
                )
                recommendations['topic_based'] = [
                    (rec[0], self._get_work_details(rec[0]))
                    for rec in content_recs
                ]
            
            # Calculate hybrid scores
            scored_recommendations = self.score_calculator.calculate_hybrid_score(
                recommendations,
                base_work
            )
            
            # Get top recommendations with score explanations
            top_recommendations = []
            for work_score in scored_recommendations[:limit]:
                work_details = self._get_work_details(work_score.work_id)
                work_details['score_explanation'] = (
                    self.score_calculator.get_score_explanation(work_score)
                )
                top_recommendations.append(work_details)
            
            execution_time = time.time() - start_time
            
            return {
                "recommendations": top_recommendations,
                "strategies_used": list(recommendations.keys()),
                "execution_time": round(execution_time, 3)
            }

        except Exception as e:
            logger.error(f"Error getting recommendations: {str(e)}", exc_info=True)
            raise
Last edited just now