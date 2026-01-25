from utils.llm_helper import call_agent
from src.agent.state import AgentState
from src.models.CandidateSchema import ServiceCandidate

def extract_information(state: AgentState) -> ServiceCandidate:
    searchplan - state.searchplan
    