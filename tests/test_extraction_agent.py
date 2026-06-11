from src.agent.graph import run_agent
from src.models.FormConfig import FormConfig

test_config = FormConfig(
    service_type="Plumber",  # The type of service requested
    location_city="Abuja",  # The city in Nigeria where the service is requested
    location_area="Gwarimpa",  # The area within the city where the service is needed
    urgency="IMMEDIATELY",  # The urgency of the request
    budget="MEDIUM",  # Budget range for the service
    additional_details="Leakage from the bathroom pipe near the sink."  # Additional details about the service
)

ans = run_agent(test_config)
print(ans)