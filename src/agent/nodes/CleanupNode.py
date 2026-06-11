"""
Node 4: Normalization & Cleanup

Three sequential steps — each reduces noise before the next runs:
  1. Completeness ranking (programmatic) — keep the best 10 candidates
  2. Logical validation (LLM)           — flag profiles a human would distrust
  3. Semantic deduplication (LLM)       — collapse same-business duplicates

If candidates reach zero after any step, synthesis_reason is set so
RankingSynthesisNode can return a meaningful message.
"""

import logging
from typing import List
from pydantic import BaseModel, Field

from src.agent.state import AgentState
from src.models.RawCandidate import RawCandidate
from utils.llm_helper import call_structured_llm
from core.config import Config

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 10

# ── LLM output schemas ────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    valid_indices: List[int] = Field(
        description="Indices (0-based) of candidates that pass logical validation"
    )


class DedupResult(BaseModel):
    keep_indices: List[int] = Field(
        description="Indices (0-based) of candidates to keep — one representative per duplicate group"
    )


# ── Prompts ───────────────────────────────────────────────────────────────────

_VALIDATION_PROMPT = """
You are a data quality reviewer for a Nigerian local services platform.

Search context — Service: {service} | City: {city} | Area: {area}

Review each candidate below and flag any that a human would reasonably distrust:
- Location clearly does not match the search city or area
- Phone number is incomplete or invalid for Nigeria
  (valid formats: 11-digit starting with 0, e.g. 08012345678, or +234 followed by 10 digits)
- Business name has no relation to the requested service
- Any other obvious data quality issue (e.g. the address is a different country)

When in doubt, keep the candidate. Only reject clear failures.

Candidates (0-indexed):
{candidates}

Return the indices of candidates that PASS.
"""

_DEDUP_PROMPT = """
You are deduplicating a list of service provider candidates.

Identify candidates that refer to the same real-world business — same name variant,
same phone, or same address. For each duplicate group, keep the candidate with the
most complete profile (most non-empty fields). If tied, keep the lower index.

Candidates (0-indexed):
{candidates}

Return the indices of candidates to KEEP.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format(candidates: List[RawCandidate]) -> str:
    lines = []
    for i, c in enumerate(candidates):
        lines.append(
            f"[{i}] Name: {c.name} | Phones: {c.phones} | "
            f"Location: {c.location} | Tags: {c.service_tags} | Source: {c.source}"
        )
    return "\n".join(lines)


def _best_candidates(candidates: List[RawCandidate], limit: int = MAX_CANDIDATES) -> List[RawCandidate]:
    return sorted(
        candidates,
        key=lambda c: (c.completeness_score(), c.rating or 0, c.name.lower()),
        reverse=True,
    )[:limit]


def _llm_filter(candidates: List[RawCandidate], prompt: str, schema) -> List[RawCandidate]:
    """Run an LLM filter and return the surviving candidates. Non-blocking on failure."""
    try:
        llm = call_structured_llm(outputschema=schema, model=Config.BASE_MODEL, temperature=0.1)
        result = llm.invoke(prompt)
        indices = result.valid_indices if hasattr(result, "valid_indices") else result.keep_indices
        return [candidates[i] for i in indices if i < len(candidates)]
    except Exception as e:
        logger.warning(f"LLM cleanup step failed, skipping: {e}")
        return candidates  # pass-through on failure


# ── Main node ─────────────────────────────────────────────────────────────────

def cleanup(state: AgentState) -> AgentState:
    candidates = state.raw_candidates
    logger.info("=" * 60)
    logger.info("NODE 4 | Cleanup")
    logger.info(f"  Input: {len(candidates)} raw candidates")

    if not candidates:
        logger.info("  No candidates to process — skipping")
        logger.info("NODE 4 | Complete")
        return state

    # Step 1: keep the highest-signal candidates without hard-rejecting sparse profiles
    before = len(candidates)
    candidates = _best_candidates(candidates)
    trimmed = before - len(candidates)
    logger.info(f"  [Step 1] Completeness ranking: trimmed {trimmed}, kept {len(candidates)}")

    if not candidates:
        logger.info("  [Step 1] All candidates dropped — routing to synthesis with reason: failed_validation")
        state.synthesis_reason = "failed_validation"
        logger.info("NODE 4 | Complete")
        return state

    config = state.config
    intent = state.intent
    service = intent.resolved_service if intent else config.service_type

    # Step 2: LLM logical validation
    logger.info(f"  [Step 2] Logical validation via LLM ({len(candidates)} candidates)")
    validation_prompt = _VALIDATION_PROMPT.format(
        service=service,
        city=config.location_city,
        area=config.location_area,
        candidates=_format(candidates),
    )
    before = len(candidates)
    candidates = _llm_filter(candidates, validation_prompt, ValidationResult)
    logger.info(f"  [Step 2] Logical validation: dropped {before - len(candidates)}, kept {len(candidates)}")

    if not candidates:
        logger.info("  [Step 2] All candidates failed validation — routing to synthesis with reason: failed_validation")
        state.synthesis_reason = "failed_validation"
        logger.info("NODE 4 | Complete")
        return state

    # Step 3: LLM semantic deduplication
    logger.info(f"  [Step 3] Semantic deduplication via LLM ({len(candidates)} candidates)")
    dedup_prompt = _DEDUP_PROMPT.format(candidates=_format(candidates))
    before = len(candidates)
    candidates = _llm_filter(candidates, dedup_prompt, DedupResult)
    logger.info(f"  [Step 3] Deduplication: dropped {before - len(candidates)}, kept {len(candidates)}")

    if not candidates:
        logger.info("  [Step 3] All candidates removed in dedup — routing to synthesis with reason: failed_validation")
        state.synthesis_reason = "failed_validation"
        logger.info("NODE 4 | Complete")
        return state

    state.clean_candidates = candidates
    logger.info(f"  Output: {len(candidates)} clean candidates passing to ranking")
    logger.info("NODE 4 | Complete")
    return state
