from pydantic import BaseModel, Field
from typing import Literal  
from langchain_core.messages import HumanMessage
from src.models.FormConfig import FormConfig

from src.models.CandidateSchema import ServiceCandidate

class AgentState(BaseModel):
    config : FormConfig
    candidates_search_history: list[ServiceCandidate]
    message_history: list[HumanMessage]
    sources: list[str]
    final_response: list[ServiceCandidate]
    summary: str