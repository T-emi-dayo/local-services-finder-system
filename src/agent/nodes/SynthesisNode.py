from typing import Dict

from src.agent.state import AgentState
from utils.llm_helper import generate_text_response
from core.config import Config
from src.models.FinalResponse import FinalResponse


Model = Config.SYNTHESIS_MODEL
Temperature = Config.SYNTHESIS_TEMP

def synthesize(state: AgentState) -> AgentState:
    candidates = state.candidates_search_history
    search_params = state.config
    
    prompt = Config.SYNTHESIS_PROMPT.format(candidates=candidates, search_params=search_params)
    
    response = generate_text_response(model= Model,
                                      temperature= Temperature, 
                                      prompt= prompt,
                                      outputschema= FinalResponse)
    
    state.final_candidates = response.candidates
    state.summary = response.summary
    
    return state