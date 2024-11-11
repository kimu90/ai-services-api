from pydantic import BaseModel
from typing import List
from typing import Optional

class SimilarExpert(BaseModel):
    orcid: str
    name: str
    shared_field: List[str]  
    shared_subfield: List[str] 
    

class ExpertBase(BaseModel):
    orcid: str

class ExpertCreate(ExpertBase):
    pass  # This remains as is, requiring only orcid

class ExpertResponse(BaseModel):
    orcid: str
    orcid: str
    name: str
    shared_field: str
    shared_subfield: str
