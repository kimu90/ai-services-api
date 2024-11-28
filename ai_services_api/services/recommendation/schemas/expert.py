from pydantic import BaseModel, Field
from typing import List, Optional

from typing import Dict, List
class SimilarExpert(BaseModel):
    orcid: str
    name: str
    shared_field_count: int = Field(0, description="Number of shared fields")
    shared_subfield_count: int = Field(0, description="Number of shared subfields")
    similarity_score: float = Field(0, description="Recommendation similarity score")

class ExpertBase(BaseModel):
    orcid: str

class ExpertCreate(ExpertBase):
    pass

class ExpertResponse(BaseModel):
    orcid: str
    name: str
    domains_fields_subfields: List[Dict[str, str]]
    similar_experts: List[SimilarExpert]