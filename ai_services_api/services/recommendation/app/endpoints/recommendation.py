from fastapi import APIRouter, HTTPException
from typing import List
from ai_services_api.services.recommendation.schemas.expert import ExpertCreate, ExpertResponse, SimilarExpert
from ai_services_api.services.recommendation.services.initial_expert_service import ExpertService
from ai_services_api.services.recommendation.services.expert_service import ExpertsService

import logging

router = APIRouter()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("/", response_model=ExpertResponse)
async def create_expert(expert: ExpertCreate):
    """Add a new expert to the recommendation system"""
    service = ExpertsService()
    result = await service.add_expert(expert.orcid)
    if not result:
        logger.error(f"Expert not found in OpenAlex for ORCID: {expert.orcid}")
        raise HTTPException(status_code=404, detail="Expert not found in OpenAlex")
    return result

@router.get("/", response_model=List[SimilarExpert])
async def get_similar_experts(orcid: str, limit: int = 10):
    """Get similar experts for a given ORCID"""
    service = ExpertService()
    similar_experts = service.get_similar_experts(orcid, limit)

    # Log the raw result for debugging purposes
    logger.debug(f"Raw query result: {similar_experts}")

    if not similar_experts:
        logger.warning(f"No similar experts found for ORCID: {orcid}")
        raise HTTPException(status_code=404, detail="No similar experts found")

    return similar_experts