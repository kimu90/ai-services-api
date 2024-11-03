from ai_services_api.services.recommendation.core.graph_connector import GraphConnector
from ai_services_api.services.recommendation.core.recommendation_strategies import RecommendationStrategies
from ai_services_api.services.recommendation.core.data_enrichment import DataEnricher
import time
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RecommendationService:
    def __init__(self):
        self.connector = GraphConnector()
        self.strategies = RecommendationStrategies(self.connector)
        self.enricher = DataEnricher(self.connector)
        
    async def get_recommendations(
        self,
        author_id: Optional[str] = None,
        work_id: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        try:
            if author_id:
                recommendations = self.strategies.get_collaborative_recommendations(
                    author_id, limit
                )
                strategy = "collaborative"
            elif work_id:
                recommendations = self.strategies.get_content_based_recommendations(
                    work_id, limit
                )
                strategy = "content-based"
            else:
                raise ValueError("Either author_id or work_id must be provided")

            response = []
            for rec in recommendations:
                work_details = self._get_work_details(rec[0])  # rec[0] is work_id
                response.append(work_details)

            execution_time = time.time() - start_time
            
            return {
                "recommendations": response,
                "strategy_used": strategy,
                "execution_time": round(execution_time, 3)
            }
        
        except Exception as e:
            logger.error(f"Error getting recommendations: {str(e)}", exc_info=True)
            raise

    def _get_work_details(self, work_id: str) -> Dict[str, Any]:
        query = """
        MATCH (w:Work {work_id: $work_id})
        OPTIONAL MATCH (w)-[:RELATED_TO]->(t:Topic)
        RETURN w.work_id, w.title, 
                COLLECT(t.topic_name) as topics,
                w.impact_score, w.citation_count
        """
        result = self.connector.graph.query(query, params={'work_id': work_id})
        if not result.result_set:
            raise ValueError(f"Work {work_id} not found")
            
        row = result.result_set[0]
        return {
            "work_id": row[0],
            "title": row[1],
            "topics": row[2],
            "impact_score": float(row[3]) if row[3] is not None else 0.0,
            "citation_count": int(row[4]) if row[4] is not None else 0
        }