from pydantic import BaseModel
from typing import List
from typing import Optional

class SimilarExpert(BaseModel):
    orcid: str
    name: str
    domains: List[str]  
    

class ExpertBase(BaseModel):
    orcid: str

class ExpertCreate(ExpertBase):
    orcid: str

class ExpertResponse(BaseModel):
    orcid: str
    orcid: str
    name: str
    shared_field: str
    shared_subfield: str
