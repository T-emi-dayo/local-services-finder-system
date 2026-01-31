from utils.llm_helper import call_agent, call_llm
from langchain.agents import create_agent

from core.config import Config
from src.agent.state import AgentState
from src.models.CandidateSchema import ServiceCandidate

from src.tools.current_time_tool import get_current_time_api
from src.tools.web_search_tool import search_web
from src.tools.search_business import search_local_businesses
from src.tools.map_search_tool import search_location
from src.tools.search_business import search_local_businesses
from src.tools.search_business_details import get_business_details
from src.tools.review_checking_tool import get_business_reviews

# Tools
from core.config import Config
from src.agent.state import AgentState

# Tools
tools = [
    search_web,
    get_current_time_api,
    search_location,
    search_local_businesses,
    get_business_details,
    get_business_reviews
]

llm = call_llm( model= Config.BASE_MODEL, temperature=Config.BASE_TEMPERATURE)

prompt = Config.EXTRACTION_PROMPT

agent = create_agent(model= Config.EXTRACTION_MODEL,
                     system_prompt =prompt,
                     tools=tools,
                     response_format= ServiceCandidate,
                     debug= True)

def service_agent(state: AgentState) -> AgentState:
    config = state.config
    
    input_data = {
        "service_type" : config.service_type,
        "location_city" : config.location_city,
        "location_area" : config.location_area,
        "urgency" : config.urgency,
        "budget" : config.budget,
        "additional_details" : config.additional_details
    }

    try:
        response = agent.invoke({"messages": [{"role": "user", "content": "I need to extract service candidate information based on the following details: " + str(input_data)}]})

        state.candidates_search_history.append(response)
        return state

    except Exception as e:
        print(f"Error during agent execution: {e}")
        return None
