from pydantic import BaseModel
from typing import List
from src.models.CandidateSchema import ServiceCandidate

class FinalResponse(BaseModel):
    summary: str
    candidates: List[ServiceCandidate]