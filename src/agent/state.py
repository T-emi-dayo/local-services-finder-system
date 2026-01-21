from pydantic import BaseModel, Field
from typing import Literal  
from src.models.FormConfig import FormConfig

class AgentState(BaseModel):
    config : FormConfig
    candidates: list[str]
    searchplan_history: list[str]
    current_searchplan: str
    