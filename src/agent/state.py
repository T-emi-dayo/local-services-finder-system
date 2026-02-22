from pydantic import BaseModel, Field
from typing import Literal  
from langchain_core.messages import HumanMessage
from src.models.FormConfig import FormConfig

from src.models.CandidateSchema import ServiceCandidate

class AgentState(BaseModel):
    config : FormConfig = Field(description="The form configuration containing user input and query parameters.")
    candidates_search_history: list[ServiceCandidate] = Field(description="List of service candidates discovered during the search.")
    message_history: list[HumanMessage] = Field(description="Conversation history containing all user messages and interactions.")
    sources: list[str] = Field(description="List of sources (URLs/references) from which information was retrieved.")
    final_candidates: list[ServiceCandidate] = Field(default=None, description="The final list of candidates selected by the agent.")
    summary: str = Field(description="Summary of the search results and findings.")