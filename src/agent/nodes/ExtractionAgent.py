from utils.llm_helper import call_agent, call_llm
from langchain_classic.agents import AgentExecutor
from langchain.agents import create_agent
from langchain_core.prompts import PromptTemplate

from core.config import Config
from src.agent.state import AgentState
from src.models.CandidateSchema import ServiceCandidate
from src.tools.current_time_tool import get_current_time_api
from src.tools.web_search_tool import search_web
from src.tools.osm_tool import search_nigerian_businesses_osm
from src.tools.map_search_tool import search_location
from src.tools.data_enrichment_tool import enrich_data

# Tools
from langchain_core.prompts import PromptTemplate

from core.config import Config
from src.agent.state import AgentState

# Tools
tools = [
    search_web,
    get_current_time_api,
    search_nigerian_businesses_osm,
    search_location,
    enrich_data
]

llm = call_llm( model= Config.BASE_MODEL, temperature=Config.BASE_TEMPERATURE)

prompt = PromptTemplate.from_template(Config.EXTRACTION_PROMPT)

agent = create_agent(model= "gpt-4o",
                     system_prompt =prompt,
                     tools=tools,
                     response_format= ServiceCandidate)

def extract_information(state: AgentState):
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

    try:
        response = agent.invoke(prompt)
        output = response.get("output")

        state.candidates.append(output)
        return output

    except Exception as e:
        print(f"Error during agent execution: {e}")
        return None
