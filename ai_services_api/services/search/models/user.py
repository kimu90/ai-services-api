from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserPreferences(BaseModel):
    preferred_topics: List[str] = []
    expertise_level: str = "intermediate"
    language: str = "en"

class User(BaseModel):
    id: str = Field(..., description="Unique identifier for the user")
    email: EmailStr
    name: str
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    search_history: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)