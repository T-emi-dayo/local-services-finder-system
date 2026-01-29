from src.agent.nodes.QueryPlanner import plan_query
from src.agent.nodes.ExtractionAgent import extract_information

from src.models.FormConfig import FormConfig
from src.agent.state import AgentState

# Test configuration instance (representing a real user request)
test_config = FormConfig(
    service_type="Plumber",  # The type of service requested
    location_city="Abuja",  # The city in Nigeria where the service is requested
    location_area="Gwarimpa",  # The area within the city where the service is needed
    urgency="IMMEDIATELY",  # The urgency of the request
    budget="MEDIUM",  # Budget range for the service
    additional_details="Leakage from the bathroom pipe near the sink."  # Additional details about the service
)

agentstate = AgentState(
    config= test_config,
    candidates = [],
    search_history = [],
)


candidates = extract_information(agentstate)
print("Extracted Candidates:", candidates)