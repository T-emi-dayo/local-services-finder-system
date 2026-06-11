"""
Node 5: Ranking & Synthesis

Ranks clean candidates against explicit criteria and produces a final response.
The ranking rationale per candidate doubles as the user-facing evidence text.

If clean_candidates is empty, returns a contextual message based on
state.synthesis_reason so the user understands why no results were returned.
"""

import logging
from typing import List
from pydantic import BaseModel, Field

from src.agent.state import AgentState
from src.models.RawCandidate import RawCandidate
from utils.llm_helper import call_structured_llm
from core.config import Config

logger = logging.getLogger(__name__)

TOP_N = 10

_NO_RESULT_MESSAGES = {
    "not_found": (
        "No service providers were found for your search. "
        "This may be due to limited listings in your area — try a nearby area or a broader service term."
    ),
    "failed_validation": (
        "Providers were found but none passed our quality checks. "
        "Data in your area may be sparse. Please try again or search a neighbouring area."
    ),
    "system_error": (
        "An unexpected error occurred during the search. Please try again."
    ),
}

# ── LLM schema ────────────────────────────────────────────────────────────────

class RankedCandidate(BaseModel):
    name: str = Field(description="Candidate name, must match exactly")
    evidence: str = Field(description="2-3 sentence rationale explaining why this provider was selected")


class FinalRanking(BaseModel):
    ranked: List[RankedCandidate] = Field(description=f"Top candidates in ranked order, max {TOP_N}")
    summary: str = Field(description="2-3 sentence overall summary of what was found and why these providers stand out")


# ── Prompt ────────────────────────────────────────────────────────────────────

_RANKING_PROMPT = """
You are selecting the best service providers for a customer's request.

Request:
- Service: {service}
- City: {city}
- Area: {area}
- Urgency: {urgency}
- Budget: {budget}

Rank the candidates below and select the top {top_n}. Apply these criteria in order:
1. Profile completeness — providers with name, phone, location, and service tags rank higher
2. Budget alignment — LOW budget → prefer LOW/MID price_signal; HIGH/NO_BUDGET → any price
3. Service tag relevance — how closely the provider's tags match the requested service
4. Location match — providers in or nearest to the requested area rank higher

For each selected candidate, write a 2-3 sentence evidence note explaining why it was chosen.
Write a 2-3 sentence overall summary of the search results.

Candidates:
{candidates}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format(candidates: List[RawCandidate]) -> str:
    lines = []
    for i, c in enumerate(candidates):
        lines.append(
            f"[{i}] Name: {c.name} | Phones: {c.phones} | Location: {c.location} "
            f"| Price: {c.price_signal} | Tags: {c.service_tags} "
            f"| Rating: {c.rating} | Reviews: {c.reviews_summary or 'N/A'}"
        )
    return "\n".join(lines)


def _fallback_rank(candidates: List[RawCandidate]) -> List[RawCandidate]:
    return sorted(
        candidates,
        key=lambda c: (c.completeness_score(), c.rating or 0, c.name.lower()),
        reverse=True,
    )[:TOP_N]


# ── Main node ─────────────────────────────────────────────────────────────────

def rank_and_synthesize(state: AgentState) -> AgentState:
    candidates = state.clean_candidates
    logger.info("=" * 60)
    logger.info("NODE 5 | Ranking & Synthesis")

    if not candidates:
        reason = state.synthesis_reason
        logger.info(f"  No candidates — returning no-result message (reason: {reason})")
        state.summary = _NO_RESULT_MESSAGES.get(reason, _NO_RESULT_MESSAGES["system_error"])
        state.final_candidates = []
        logger.info("NODE 5 | Complete")
        return state

    config = state.config
    intent = state.intent
    service = intent.resolved_service if intent else config.service_type
    logger.info(f"  Ranking {len(candidates)} candidates for service='{service}'")

    try:
        llm = call_structured_llm(
            outputschema=FinalRanking,
            model=Config.SYNTHESIS_MODEL,
            temperature=Config.SYNTHESIS_TEMP,
        )

        prompt = _RANKING_PROMPT.format(
            service=service,
            city=config.location_city,
            area=config.location_area,
            urgency=config.urgency,
            budget=config.budget,
            top_n=TOP_N,
            candidates=_format(candidates),
        )

        ranking = llm.invoke(prompt)

        name_map = {c.name.lower(): c for c in candidates}
        final = []
        for rc in ranking.ranked:
            raw = name_map.get(rc.name.lower())
            if raw:
                raw.evidence = rc.evidence
                final.append(raw)
                logger.info(f"  Ranked #{len(final)}: '{raw.name}'")

        if not final:
            logger.warning("  LLM ranking returned no matching candidates; using deterministic fallback ranking")
            final = _fallback_rank(candidates)
            for raw in final:
                raw.evidence = "Selected from the strongest available local search results based on profile completeness, rating, and relevance signals."

        state.final_candidates = final
        state.summary = ranking.summary
        state.synthesis_reason = "success"
        logger.info(f"  Output: {len(final)} final candidates selected")

    except Exception as e:
        logger.warning(f"  Ranking/synthesis failed; using deterministic fallback ranking: {e}")
        final = _fallback_rank(candidates)
        for raw in final:
            raw.evidence = "Selected from the strongest available local search results based on profile completeness, rating, and relevance signals."
        state.synthesis_reason = "success" if final else "system_error"
        state.summary = (
            f"Found {len(final)} local provider candidate(s). "
            "They are ordered by the strongest available profile signals."
            if final else _NO_RESULT_MESSAGES["system_error"]
        )
        state.final_candidates = final

    logger.info("NODE 5 | Complete")
    return state
