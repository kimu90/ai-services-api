from fastapi import APIRouter, Depends, HTTPException
from ai_services_api.services.recommendation.services.recommendation_service import RecommendationService
from ai_services_api.services.recommendation.utils.dependencies import get_recommendation_service
from typing import Optional

router = APIRouter()

@router.get("/recommendation")
async def get_recommendations(
    service: RecommendationService = Depends(get_recommendation_service),
    author_id: Optional[str] = None,
    work_id: Optional[str] = None,
    limit: int = 5
):
    try:
        recommendations = await service.get_recommendations(
            author_id=author_id,
            work_id=work_id,
            limit=limit
        )
        return recommendations
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")