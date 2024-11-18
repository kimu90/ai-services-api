from typing import List, Optional
from pydantic import BaseModel, Field

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1)
    filters: Optional[dict] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    user_id: Optional[str] = None

class SearchResult(BaseModel):
    id: str
    title: str
    content: str
    relevance_score: float
    highlights: List[str] = []
    source_url: Optional[str] = None
    tags: List[str] = []

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    page: int
    page_size: int
    suggestions: List[str] = []