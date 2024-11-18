from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class Document(BaseModel):
    id: str = Field(..., description="Unique identifier for the document")
    title: str
    content: str
    embedding: Optional[List[float]] = None
    tags: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)