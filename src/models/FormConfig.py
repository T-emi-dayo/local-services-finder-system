from pydantic import BaseModel
from typing import Literal


class FormConfig(BaseModel):
    service_type: str # (e.g., “Plumber”, “Vulcanizer”, “Generator repair”)
    location_city: str # (e.g., “Lagos”, “Abuja”, “Port Harcourt”)
    location_area : str # (e.g., “Ikeja”, "Gwarimpa", “Yaba”, “Victoria Island”)
    urgency : Literal["IMMEDIATELY", "TODAY", "THIS_WEEK", "NOT_URGENT"]
    budget : Literal["LOW", "MEDIUM", "HIGH", "NO_BUDGET"]
    additional_details: str = None  # (Optional additional details about the service request)