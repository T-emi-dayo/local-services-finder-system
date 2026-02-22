from pydantic import BaseModel, Field
from typing import List
from src.models.CandidateSchema import ServiceCandidate

class FinalResponse(BaseModel):
    summary: str = Field(description="A summary of the search results and findings.")
    candidates: List[ServiceCandidate] = Field(description="List of service candidates that match the user's query.")