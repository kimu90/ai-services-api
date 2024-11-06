from fastapi import APIRouter, HTTPException
from typing import List
from ai_services_api.services.recommendation.schemas.expert import ExpertCreate, ExpertResponse, SimilarExpert
from ai_services_api.services.recommendation.services.expert_service import ExpertService

router = APIRouter()

@router.post("/", response_model=ExpertResponse)
async def create_expert(expert: ExpertCreate):
    """Add a new expert to the recommendation system"""
    service = ExpertService()
    result = await service.add_expert(expert.orcid)
    if not result:
        raise HTTPException(status_code=404, detail="Expert not found in OpenAlex")
    return result

@router.get("/", response_model=List[SimilarExpert])  
async def get_similar_experts(orcid: str, limit: int = 10):
    """Get similar experts for a given ORCID"""
    service = ExpertService()
    
    # Call the service method to get similar experts
    similar_experts = service.get_similar_experts(orcid, limit)

    # Log the raw result for debugging purposes
    print("Raw query result:", similar_experts)

    # If the result is empty, raise an HTTPException with a 404 error
    if not similar_experts:
        raise HTTPException(status_code=404, detail="No similar experts found")

    # The similar_experts list already contains SimilarExpert objects,
    # so we can return it directly
    return similar_experts