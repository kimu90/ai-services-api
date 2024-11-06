from pydantic import BaseModel
from typing import List

class SimilarExpert(BaseModel):
    orcid: str
    name: str
    similarity_score: float

class ExpertBase(BaseModel):
    orcid: str

class ExpertCreate(ExpertBase):
    pass  # This remains as is, requiring only orcid

class ExpertResponse(BaseModel):
    orcid: str
    similar_experts: List[SimilarExpert] = []
