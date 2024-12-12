from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
from ai_services_api.services.recommendation.services.expert_matching import ExpertMatchingService
from ai_services_api.services.recommendation.core.database import Neo4jDatabase

router = APIRouter()
logger = logging.getLogger(__name__)

class ExpertBase(BaseModel):
    expert_id: str = Field(..., description="Expert's unique identifier")

class ExpertResponse(ExpertBase):
    name: str = Field(..., description="Expert's full name")
    expertise_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of expert's expertise categories"
    )
    similar_experts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of similar experts with similarity scores"
    )
    collaboration_suggestions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Suggested collaborators based on complementary expertise"
    )

class ExpertiseAnalysis(BaseModel):
    domains: List[str] = Field(default_factory=list)
    research_areas: List[str] = Field(default_factory=list)
    technical_skills: List[str] = Field(default_factory=list)
    applications: List[str] = Field(default_factory=list)
    related_fields: List[str] = Field(default_factory=list)

class CollaborationRecommendation(BaseModel):
    expert_id: str
    name: str
    matched_domains: int
    matched_skills: int
    collaboration_score: float
    recommendation_reason: str

def get_expert_service():
    """Dependency for expert matching service"""
    service = ExpertMatchingService()
    try:
        yield service
    finally:
        service.close()

def get_db():
    """Dependency for Neo4j database"""
    db = Neo4jDatabase()
    try:
        yield db
    finally:
        db.close()

@router.get("/experts/{expert_id}", response_model=ExpertResponse)
async def get_expert_profile(
    expert_id: str,
    service: ExpertMatchingService = Depends(get_expert_service),
    db: Neo4jDatabase = Depends(get_db)
):
    """
    Get comprehensive expert profile with similarity matches and collaboration suggestions
    """
    try:
        # Get expertise summary
        expertise_summary = await db.get_expertise_summary(expert_id)
        if not expertise_summary:
            raise HTTPException(
                status_code=404,
                detail=f"Expert with ID {expert_id} not found"
            )

        # Get similar experts
        similar_experts = await service.find_similar_experts(expert_id)

        # Get collaboration recommendations
        collaboration_suggestions = await service.get_collaboration_recommendations(expert_id)

        return ExpertResponse(
            expert_id=expert_id,
            name=expertise_summary.get("name", ""),
            expertise_summary=expertise_summary,
            similar_experts=similar_experts,
            collaboration_suggestions=collaboration_suggestions
        )

    except Exception as e:
        logger.error(f"Error retrieving expert profile: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving expert profile"
        )

@router.get("/experts/{expert_id}/analyze", response_model=ExpertiseAnalysis)
async def analyze_expert_expertise(
    expert_id: str,
    service: ExpertMatchingService = Depends(get_expert_service),
    db: Neo4jDatabase = Depends(get_db)
):
    """
    Analyze expert's expertise using Gemini API
    """
    try:
        # Get expert's expertise data
        expertise_summary = await db.get_expertise_summary(expert_id)
        if not expertise_summary:
            raise HTTPException(
                status_code=404,
                detail=f"Expert with ID {expert_id} not found"
            )

        # Combine all expertise items
        expertise_items = (
            expertise_summary.get("domains", []) +
            expertise_summary.get("fields", []) +
            expertise_summary.get("skills", [])
        )

        # Analyze using Gemini
        analysis = await service.analyze_expertise(expertise_items)
        return ExpertiseAnalysis(**analysis)

    except Exception as e:
        logger.error(f"Error analyzing expert expertise: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while analyzing expertise"
        )

@router.get("/experts/{expert_id}/collaborations", response_model=List[CollaborationRecommendation])
async def get_collaboration_recommendations(
    expert_id: str,
    min_score: float = Query(0.5, ge=0.0, le=1.0),
    service: ExpertMatchingService = Depends(get_expert_service)
):
    """
    Get detailed collaboration recommendations with explanation
    """
    try:
        recommendations = await service.get_collaboration_recommendations(expert_id)
        
        # Filter and format recommendations
        formatted_recommendations = []
        for rec in recommendations:
            if rec["collaboration_score"] >= min_score:
                formatted_recommendations.append(
                    CollaborationRecommendation(
                        expert_id=rec["id"],
                        name=rec["name"],
                        matched_domains=rec["matched_domains"],
                        matched_skills=rec["matched_skills"],
                        collaboration_score=rec["collaboration_score"],
                        recommendation_reason=f"Shares {rec['matched_domains']} domains and {rec['matched_skills']} skills"
                    )
                )

        return formatted_recommendations

    except Exception as e:
        logger.error(f"Error getting collaboration recommendations: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while getting recommendations"
        )

@router.get("/experts/{expert_id1}/connection/{expert_id2}")
async def find_expert_connection(
    expert_id1: str,
    expert_id2: str,
    max_depth: int = Query(3, ge=1, le=5),
    db: Neo4jDatabase = Depends(get_db)
):
    """
    Find connection paths between two experts
    """
    try:
        paths = await db.find_expertise_paths(expert_id1, expert_id2, max_depth)
        if not paths:
            return {
                "message": "No connection found between the experts",
                "paths": []
            }
        
        return {
            "message": f"Found {len(paths)} connection paths",
            "paths": paths
        }

    except Exception as e:
        logger.error(f"Error finding expert connections: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while finding connections"
        )
