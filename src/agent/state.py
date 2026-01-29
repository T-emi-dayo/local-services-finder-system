from pydantic import BaseModel, Field
from typing import Literal  
from src.models.FormConfig import FormConfig
from src.models.CandidateSchema import ServiceCandidate

class AgentState(BaseModel):
    config : FormConfig
    candidates: list[ServiceCandidate]
    search_history: list[str]
    