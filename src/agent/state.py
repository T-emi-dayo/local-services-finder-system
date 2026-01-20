from pydantic import BaseModel, Field
from typing import Literal  
from src.models.FormConfig import FormConfig

class AgentState(BaseModel):
    config = FormConfig
    