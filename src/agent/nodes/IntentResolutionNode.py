"""
Node 1+2: Intent Resolution + Search Param Generation

Single LLM call that:
  1. Validates and corrects the service type using additional_details
  2. Generates primary (area-level) and fallback (city-level) search params

On LLM failure: non-blocking — falls back to raw form values so the graph
always continues.
"""

import logging
from src.agent.state import AgentState
from src.models.SearchParams import IntentAndSearchParams
from utils.llm_helper import call_structured_llm
from core.config import Config

logger = logging.getLogger(__name__)

PROMPT = """
You are an expert service classifier for a local services finder platform in Nigeria.

Given the user's input, you must:
1. Determine the REAL service needed. The problem description (additional_details) OVERRIDES
   the stated service type when they conflict. For example, if service_type is "Electrician"
   but additional_details says "fix car air conditioning", the real service is "Auto Mechanic".
2. Generate precise search parameters for finding local providers.

User Input:
- Stated Service: {service_type}
- City: {location_city}
- Area: {location_area}
- Urgency: {urgency}
- Budget: {budget}
- Problem Description: {additional_details}

Rules:
- primary_query must be specific: include the service AND area (e.g. "generator repair Lekki Lagos")
- fallback_query must be wider: service + city only (e.g. "generator repair Lagos")
- primary_subtypes and fallback_subtypes are comma-separated Google Maps business categories
- primary_lat/primary_lng must be the actual coordinates of the area in Nigeria
- search_terms should include common synonyms (e.g. "generator repair" → ["generator repair", "generator servicing", "inverter technician"])
- Set correction_applied to true only if additional_details changed the service type
"""


def _build_fallback_intent(config) -> IntentAndSearchParams:
    """Deterministic fallback when LLM call fails. Uses raw form values."""
    return IntentAndSearchParams(
        resolved_service=config.service_type,
        search_terms=[config.service_type],
        correction_applied=False,
        primary_query=f"{config.service_type} {config.location_area} {config.location_city}",
        primary_subtypes=config.service_type,
        primary_lat=6.5244,  # Lagos default — LLM failure means we have no better info
        primary_lng=3.3792,
        fallback_query=f"{config.service_type} {config.location_city}",
        fallback_subtypes=config.service_type,
    )


def resolve_intent(state: AgentState) -> AgentState:
    config = state.config
    logger.info("=" * 60)
    logger.info("NODE 1+2 | Intent Resolution & Search Param Generation")
    logger.info(f"  Input  : service='{config.service_type}' | city='{config.location_city}' | area='{config.location_area}'")
    logger.info(f"  Urgency: {config.urgency} | Budget: {config.budget}")
    if config.additional_details:
        logger.info(f"  Details: '{config.additional_details}'")

    prompt = PROMPT.format(
        service_type=config.service_type,
        location_city=config.location_city,
        location_area=config.location_area,
        urgency=config.urgency,
        budget=config.budget,
        additional_details=config.additional_details or "Not provided",
    )

    try:
        llm = call_structured_llm(
            outputschema=IntentAndSearchParams,
            model=Config.BASE_MODEL,
            temperature=0.3,
        )
        state.intent = llm.invoke(prompt)
        if state.intent.correction_applied:
            logger.info(f"  Correction applied: '{config.service_type}' -> '{state.intent.resolved_service}'")
        else:
            logger.info(f"  Service confirmed: '{state.intent.resolved_service}'")
        logger.info(f"  Search terms: {state.intent.search_terms}")
        logger.info(f"  Primary query: '{state.intent.primary_query}'")
        logger.info(f"  Fallback query: '{state.intent.fallback_query}'")
    except Exception as e:
        logger.error(f"  LLM call failed — falling back to raw form values: {e}")
        state.intent = _build_fallback_intent(config)

    logger.info("NODE 1+2 | Complete")
    return state
