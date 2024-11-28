from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from ai_services_api.services.recommendation.schemas.expert import ExpertCreate, ExpertResponse, SimilarExpert

from ai_services_api.services.recommendation.services.expert_service import ExpertsService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/experts", response_model=Dict[str, Any])
async def create_expert(expert: ExpertCreate):
    """
    Add a new expert to the recommendation system and fetch similar experts.
    Enhanced with comprehensive error handling and logging.
    """
    try:
        service = ExpertsService()
        result = await service.add_expert(expert.orcid)

        if not result:
            logger.error(f"Expert not found or processing failed for ORCID: {expert.orcid}")
            raise HTTPException(
                status_code=404, 
                detail="Expert not found or could not be processed"
            )

        # Log successful expert addition
        logger.info(f"Successfully processed expert: {expert.orcid}")

        return {
            "expert_data": result.get('expert_data', {}),
            "domains_fields_subfields": result.get('domains_fields_subfields', []),
            "similar_experts": result.get('recommendations', [])
        }

    except Exception as e:
        logger.error(f"Unexpected error processing expert {expert.orcid}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/experts/similar", response_model=List[SimilarExpert])
async def get_similar_experts(orcid: str, limit: int = 10):
    """
    Get similar experts for a given ORCID with enhanced error handling.
    """
    try:
        service = ExpertsService()
        similar_experts = service.get_similar_experts(orcid, limit)

        if not similar_experts:
            logger.warning(f"No similar experts found for ORCID: {orcid}")
            raise HTTPException(
                status_code=404, 
                detail="No similar experts found"
            )

        logger.info(f"Retrieved {len(similar_experts)} similar experts for {orcid}")
        return similar_experts

    except Exception as e:
        logger.error(f"Error retrieving similar experts for {orcid}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")