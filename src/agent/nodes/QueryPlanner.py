from utils.llm_helper import call_structured_llm
from core.config import Config
from src.models.QueryPlanOutputSchema import ServiceSearchRequest
from src.models.FormConfig import FormConfig
from src.agent.state import AgentState


Model = Config.QUERY_MODEL
Temperature = Config.QUERY_TEMP

def plan_query(state: AgentState) -> ServiceSearchRequest:
    config = state.config
    
    input_data = {
        "service_type" : config.service_type,
        "location_city" : config.location_city,
        "location_area" : config.location_area,
        "urgency" : config.urgency,
        "budget" : config.budget,
        "additional_details" : config.additional_details
    }
    
    prompt = Config.QUERY_PLANNER_PROMPT.format(**input_data)
    
    llm = call_structured_llm(outputschema=ServiceSearchRequest,
                              model=Model,
                              temperature=Temperature)
    
    response = llm.invoke(prompt)
    
    return response