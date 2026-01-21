from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


class UrgencyLevel(str, Enum):
    IMMEDIATELY = "IMMEDIATELY"
    URGENT = "URGENT"
    SOON = "SOON"
    FLEXIBLE = "FLEXIBLE"


class BudgetBand(str, Enum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"
    PREMIUM = "PREMIUM"


class PriceSensitivity(str, Enum):
    CHEAP = "CHEAP"
    VALUE = "VALUE"
    QUALITY = "QUALITY"
    PREMIUM = "PREMIUM"


class Constraints(BaseModel):
    whatsapp_only: Optional[bool] = Field(None, description="Customer prefers WhatsApp contact")
    landmark: Optional[str] = Field(None, description="Nearby landmark for location reference")
    price_sensitivity: Optional[PriceSensitivity] = Field(None, description="Price sensitivity level")
    # Add other constraint fields as needed
    verified_only: Optional[bool] = None
    female_provider: Optional[bool] = None
    availability_hours: Optional[str] = None


class CanonicalIntent(BaseModel):
    service_type: str = Field(..., description="Type of service needed (e.g., plumber, electrician)")
    location_city: str = Field(..., description="City where service is needed")
    location_area: Optional[str] = Field(None, description="Specific area or neighborhood")
    urgency: UrgencyLevel = Field(..., description="Urgency level of the request")
    budget_band: BudgetBand = Field(..., description="Budget range")
    constraints: Optional[Constraints] = Field(None, description="Additional constraints or preferences")
    keywords: List[str] = Field(default_factory=list, description="Key terms describing the problem")


class QuerySets(BaseModel):
    maps: List[str] = Field(default_factory=list, description="Search queries for map platforms")
    web: List[str] = Field(default_factory=list, description="General web search queries")
    social: List[str] = Field(default_factory=list, description="Social media search queries")
    forum: List[str] = Field(default_factory=list, description="Forum-specific search queries")


class PlatformHints(BaseModel):
    maps_weight: float = Field(0.4, ge=0, le=1, description="Weight for maps results")
    web_weight: float = Field(0.3, ge=0, le=1, description="Weight for web results")
    social_weight: float = Field(0.2, ge=0, le=1, description="Weight for social results")
    forum_weight: float = Field(0.1, ge=0, le=1, description="Weight for forum results")


class LoopPolicy(BaseModel):
    max_rounds: int = Field(2, ge=1, description="Maximum search rounds")
    max_tool_calls: int = Field(12, ge=1, description="Maximum total tool calls")
    target_unique_candidates: int = Field(20, ge=1, description="Target number of unique candidates")
    early_stop_if_high_confidence: bool = Field(True, description="Stop early if high confidence results found")


class StopConditions(BaseModel):
    min_high_score_candidates: int = Field(5, ge=1, description="Minimum high-scoring candidates before stopping")
    high_score_threshold: float = Field(0.72, ge=0, le=1, description="Score threshold for high-quality candidates")
    time_budget_ms: int = Field(7000, ge=0, description="Time budget in milliseconds")


class RiskFlag(str, Enum):
    SCAM_SENSITIVE = "scam_sensitive"
    HEALTH_CRITICAL = "health_critical"
    FINANCIAL_RISK = "financial_risk"
    SAFETY_CONCERN = "safety_concern"
    CHILD_SAFETY = "child_safety"


class ServiceSearchRequest(BaseModel):
    canonical_intent: CanonicalIntent = Field(..., description="Structured representation of the user intent")
    query_sets: QuerySets = Field(..., description="Platform-specific search queries for user query")
    platform_hints: PlatformHints = Field(default_factory=PlatformHints, description="Platform weighting")
    loop_policy: LoopPolicy = Field(default_factory=LoopPolicy, description="Search loop configuration")
    stop_conditions: StopConditions = Field(default_factory=StopConditions, description="Conditions to stop search")
    risk_flags: List[RiskFlag] = Field(default_factory=list, description="Risk indicators for this request")

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "canonical_intent": {
                    "service_type": "plumber",
                    "location_city": "Abuja",
                    "location_area": "Gwarimpa",
                    "urgency": "IMMEDIATELY",
                    "budget_band": "MID",
                    "constraints": {
                        "whatsapp_only": True,
                        "landmark": "Near Shoprite",
                        "price_sensitivity": "CHEAP"
                    },
                    "keywords": ["leak", "burst pipe"]
                },
                "query_sets": {
                    "maps": ["plumber in Gwarimpa Abuja"],
                    "web": ["Gwarimpa plumber phone number"],
                    "social": ["plumber Gwarimpa Abuja WhatsApp"],
                    "forum": ["site:nairaland.com plumber Gwarimpa"]
                },
                "risk_flags": ["scam_sensitive"]
            }
        }


    # # Example usage:
    # if __name__ == "__main__":
    #     # Parse from dict
    #     data = {
    #         "canonical_intent": {
    #             "service_type": "plumber",
    #             "location_city": "Abuja",
    #             "location_area": "Gwarimpa",
    #             "urgency": "IMMEDIATELY",
    #             "budget_band": "MID",
    #             "constraints": {
    #                 "whatsapp_only": True,
    #                 "landmark": "...",
    #                 "price_sensitivity": "CHEAP"
    #             },
    #             "keywords": ["leak", "burst pipe"]
    #         },
    #         "query_sets": {
    #             "maps": ["plumber in Gwarimpa Abuja", "emergency plumber Gwarimpa WhatsApp"],
    #             "web": ["Gwarimpa plumber phone number", "recommended plumber Gwarimpa Abuja"],
    #             "social": ["plumber Gwarimpa Abuja WhatsApp", "any good plumber in Gwarimpa"],
    #             "forum": ["site:nairaland.com plumber Gwarimpa", "nairaland recommended plumber Abuja"]
    #         },
    #         "platform_hints": {
    #             "maps_weight": 0.45,
    #             "web_weight": 0.35,
    #             "social_weight": 0.15,
    #             "forum_weight": 0.05
    #         },
    #         "loop_policy": {
    #             "max_rounds": 2,
    #             "max_tool_calls": 12,
    #             "target_unique_candidates": 20,
    #             "early_stop_if_high_confidence": True
    #         },
    #         "stop_conditions": {
    #             "min_high_score_candidates": 5,
    #             "high_score_threshold": 0.72,
    #             "time_budget_ms": 7000
    #         },
    #         "risk_flags": ["scam_sensitive"]
    #     }
        
    #     request = ServiceSearchRequest(**data)
    #     print(request.model_dump_json(indent=2))
        
    #     # Get JSON schema for LLM
    #     print("\n=== JSON Schema ===")
    #     print(ServiceSearchRequest.model_json_schema())