from pydantic import BaseModel, Field
from typing import List, Optional

class RecommendationRequest(BaseModel):
    author_id: Optional[str] = Field(None, description="Author ID for collaborative filtering")
    work_id: Optional[str] = Field(None, description="Work ID for content-based filtering")
    limit: int = Field(default=5, ge=1, le=20, description="Number of recommendations to return")

class WorkResponse(BaseModel):
    work_id: str
    title: str
    topics: List[str]
    impact_score: float
    citation_count: int

class RecommendationResponse(BaseModel):
    recommendations: List[WorkResponse]
    strategy_used: str
    execution_time: float

class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None