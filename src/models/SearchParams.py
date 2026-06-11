from pydantic import BaseModel, Field
from typing import List


class IntentAndSearchParams(BaseModel):
    """
    Output of the combined Intent Resolution + Search Param Generation node.
    Carries the corrected service intent and all params needed to drive tool calls.
    """
    resolved_service: str = Field(description="The actual service type needed, corrected if additional_details overrides service_type")
    search_terms: List[str] = Field(description="Synonyms and related services to improve search recall")
    correction_applied: bool = Field(description="True if additional_details overrode the stated service_type")

    # Primary params - specific (area-level)
    primary_query: str = Field(description="Search query for primary tool call, e.g. 'generator repair Lekki Lagos'")
    primary_subtypes: str = Field(description="Comma-separated business subtypes for primary search")
    # primary_lat: float = Field(description="Latitude for the target area")
    # primary_lng: float = Field(description="Longitude for the target area")
    # For the location, eventually to reduce risk of hallucination, we might want to use a geocoding tool to convert the user-provided location into lat/lng, and feed that into the search params.
    # For now, we can allow the LLM to generate lat/lng directly, but we should be aware of the potential for errors there.

    # Fallback params - wider (city-level)
    fallback_query: str = Field(description="Broader query used if primary search fails quality gate")
    fallback_subtypes: str = Field(description="Broader subtypes for fallback search")
