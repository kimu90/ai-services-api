from ai_services_api.services.recommendation.services.recommendation_service import RecommendationService
from fastapi import HTTPException

_recommendation_service = None

def get_recommendation_service() -> RecommendationService:
    global _recommendation_service
    if _recommendation_service is None:
        try:
            _recommendation_service = RecommendationService()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize recommendation service"
            )
    return _recommendation_service