from pydantic import BaseModel, Field
from typing import Literal  
from src.models.FormConfig import FormConfig
from src.models.CandidateSchema import ServiceCandidate
from src.models.QueryPlanOutputSchema import ServiceSearchRequest

class AgentState(BaseModel):
    config : FormConfig
    candidates: list[ServiceCandidate]
    searchplan: ServiceSearchRequest
    searchplan_history: list[ServiceSearchRequest]
    