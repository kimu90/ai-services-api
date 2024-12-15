from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import json
from datetime import datetime
from ai_services_api.services.recommendation.services.expert_matching import ExpertMatchingService
from ai_services_api.services.recommendation.core.database import Neo4jDatabase
from ai_services_api.services.recommendation.core.postgres_database import get_db_connection

router = APIRouter()
logger = logging.getLogger(__name__)

# Base Models
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

# Dependencies
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

# Main Endpoints
@router.get("/experts/{expert_id}", response_model=ExpertResponse)
async def get_expert_profile(
    expert_id: str,
    service: ExpertMatchingService = Depends(get_expert_service),
    db: Neo4jDatabase = Depends(get_db)
):
    """Get comprehensive expert profile with similarity matches and collaboration suggestions"""
    try:
        # Get expertise summary
        expertise_summary = await db.get_expertise_summary(expert_id)
        if not expertise_summary:
            raise HTTPException(status_code=404, detail=f"Expert with ID {expert_id} not found")

        # Get similar experts
        similar_experts = await service.find_similar_experts(expert_id)

        # Get collaboration recommendations
        collaboration_suggestions = await service.get_collaboration_recommendations(expert_id)

        # Record analytics
        pg_conn = get_db_connection()
        try:
            with pg_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO expert_matching_logs (
                        expert_id, matched_expert_id, similarity_score, shared_domains
                    ) VALUES %s
                """, [(
                    expert_id,
                    expert['id'],
                    expert.get('similarity_score', 0),
                    len(expert.get('shared_domains', []))
                ) for expert in similar_experts])
                pg_conn.commit()
        finally:
            pg_conn.close()

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
    """Analyze expert's expertise using Gemini API"""
    try:
        expertise_summary = await db.get_expertise_summary(expert_id)
        if not expertise_summary:
            raise HTTPException(status_code=404, detail=f"Expert with ID {expert_id} not found")

        expertise_items = (
            expertise_summary.get("domains", []) +
            expertise_summary.get("fields", []) +
            expertise_summary.get("skills", [])
        )

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
    """Get detailed collaboration recommendations with explanation"""
    try:
        recommendations = await service.get_collaboration_recommendations(expert_id)
        
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

        # Record collaboration suggestions
        pg_conn = get_db_connection()
        try:
            with pg_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO collaboration_history (
                        expert_id, collaborator_id, collaboration_score, shared_domains
                    ) VALUES %s
                """, [(
                    expert_id,
                    rec["id"],
                    rec["collaboration_score"],
                    json.dumps({"domains": rec.get("shared_domains", [])})
                ) for rec in recommendations])
                pg_conn.commit()
        finally:
            pg_conn.close()

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
    """Find connection paths between two experts"""
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

# Test Endpoints
@router.post("/test/recommend")
async def test_expert_recommendation(
    expert_id: str,
    background_tasks: BackgroundTasks,
    min_similarity: float = 0.5
):
    """Test endpoint for expert recommendations with analytics tracking."""
    db_conn = get_db_connection()
    cursor = db_conn.cursor()
    start_time = datetime.utcnow()
    
    try:
        # Get expert matching service
        expert_matching = ExpertMatchingService()
        
        # Get recommendations with analytics tracking
        similar_experts = await expert_matching.find_similar_experts(expert_id)
        
        # Record matches in analytics
        for match in similar_experts:
            cursor.execute("""
                INSERT INTO expert_matching_logs (
                    expert_id,
                    matched_expert_id,
                    similarity_score,
                    shared_domains,
                    shared_fields,
                    shared_skills,
                    successful
                ) VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
            """, (
                expert_id,
                match['id'],
                match['similarity_score'],
                '[1]',  # Create a JSONB array with single value
                len(match.get('shared_fields', [])),
                len(match.get('shared_skills', [])),
                match['similarity_score'] >= min_similarity
            ))
            
            # Record domain analytics
            for domain in match.get('shared_domains', []):
                cursor.execute("""
                    INSERT INTO domain_expertise_analytics (
                        domain_name,
                        match_count
                    ) VALUES (%s, 1)
                    ON CONFLICT (domain_name) 
                    DO UPDATE SET match_count = domain_expertise_analytics.match_count + 1
                """, (domain,))
        
        db_conn.commit()
        
        return {
            "expert_id": expert_id,
            "recommendations": similar_experts,
            "analytics": {
                "total_matches": len(similar_experts),
                "average_similarity": sum(e['similarity_score'] for e in similar_experts) / len(similar_experts) if similar_experts else 0,
                "timestamp": datetime.utcnow()
            }
        }
        
    except Exception as e:
        db_conn.rollback()
        logger.error(f"Error in test recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        db_conn.close()

@router.get("/test/analytics/expert/{expert_id}")
async def test_get_expert_analytics(expert_id: str):
    """Get analytics for test recommendations."""
    db_conn = get_db_connection()
    cursor = db_conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_matches,
                AVG(similarity_score) as avg_similarity,
                SUM(shared_domains) as total_shared_domains,
                SUM(shared_fields) as total_shared_fields,
                SUM(shared_skills) as total_shared_skills,
                SUM(CASE WHEN successful THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
            FROM expert_matching_logs
            WHERE expert_id = %s
        """, (expert_id,))
        
        matching_metrics = cursor.fetchone()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_collaborations,
                AVG(collaboration_score) as avg_score,
                COUNT(DISTINCT collaborator_id) as unique_collaborators
            FROM collaboration_history
            WHERE expert_id = %s
        """, (expert_id,))
        
        collab_metrics = cursor.fetchone()
        
        return {
            "matching_metrics": {
                "total_matches": matching_metrics[0],
                "avg_similarity": matching_metrics[1],
                "total_shared_domains": matching_metrics[2],
                "total_shared_fields": matching_metrics[3],
                "total_shared_skills": matching_metrics[4],
                "success_rate": matching_metrics[5]
            },
            "collaboration_metrics": {
                "total_collaborations": collab_metrics[0],
                "avg_score": collab_metrics[1],
                "unique_collaborators": collab_metrics[2]
            }
        }
        
    finally:
        cursor.close()
        db_conn.close()

@router.post("/test/verify/{expert_id}")
async def verify_recommendation_data(expert_id: str):
    """Verify that test data was properly stored."""
    db_conn = get_db_connection()
    cursor = db_conn.cursor()
    
    try:
        # Verify matching logs
        cursor.execute("""
            SELECT COUNT(*) 
            FROM expert_matching_logs 
            WHERE expert_id = %s
        """, (expert_id,))
        matching_count = cursor.fetchone()[0]
        
        # Verify collaboration history
        cursor.execute("""
            SELECT COUNT(*) 
            FROM collaboration_history 
            WHERE expert_id = %s
        """, (expert_id,))
        collab_count = cursor.fetchone()[0]
        
        # Get domain interactions
        cursor.execute("""
            SELECT DISTINCT domain_name
            FROM domain_expertise_analytics
            WHERE match_count > 0
        """)
        active_domains = [row[0] for row in cursor.fetchall()]
        
        return {
            "status": "success",
            "data_verification": {
                "matching_records": matching_count,
                "collaboration_records": collab_count,
                "active_domains": len(active_domains)
            },
            "verification_time": datetime.utcnow()
        }
        
    finally:
        cursor.close()
        db_conn.close()
