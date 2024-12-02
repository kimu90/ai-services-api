from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from ai_services_api.services.recommendation.schemas.expert import (
    ExpertCreate,
    ExpertResponse,
    SimilarExpert
)
from ai_services_api.services.recommendation.services.expert_service import ExpertsService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=ExpertResponse)
async def create_expert(expert: ExpertCreate):
    """
    Add a new expert to the recommendation system and fetch similar experts.
    """
    logger.info(f"Processing new expert request for ORCID: {expert.orcid}")
    
    try:
        service = ExpertsService()
        result = await service.add_expert(expert.orcid)
        
        if not result:
            logger.error(f"Expert not found or processing failed for ORCID: {expert.orcid}")
            raise HTTPException(
                status_code=404,
                detail=f"Expert with ORCID {expert.orcid} not found or could not be processed"
            )
        
        response = ExpertResponse(
            orcid=expert.orcid,
            name=result["expert_data"].get("display_name", "Unknown"),
            domains_fields_subfields=result.get("domains_fields_subfields", []),
            similar_experts=result.get("recommendations", [])
        )
        
        logger.info(f"Successfully processed expert: {expert.orcid}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing expert {expert.orcid}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while processing expert: {str(e)}"
        )
@router.get("/", response_model=List[SimilarExpert])
async def get_similar_experts(
    orcid: str,
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of similar experts to return")
):
    """
    Get similar experts based on shared domains
    """
    try:
        service = ExpertsService()
        similar_experts = service.get_similar_experts(orcid, limit)

        if not similar_experts:
            logger.warning(f"No similar experts found for ORCID: {orcid}")
            return []

        logger.info(f"Retrieved {len(similar_experts)} similar experts for {orcid}")
        return similar_experts

    except Exception as e:
        logger.error(f"Error retrieving similar experts for {orcid}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving similar experts"
        )