"""
Node 3: Tool Orchestration

Tier 1 - Candidate discovery (sequential, primary then optional fallback):
  search_local_businesses → normalize → fallback/relaxed search if needed

Tier 2 - Per-candidate enrichment (runs for each candidate with a business_id):
  get_business_details → update RawCandidate
  get_business_reviews → update RawCandidate.reviews_summary

Quality gate: prefer up to 10 candidates, but proceed with whatever local search finds.
Fallback searches are broader and less parameter-restrictive so the graph is more likely
to return useful output.
"""

import logging
from typing import List, Optional

from src.agent.state import AgentState
from src.models.RawCandidate import RawCandidate
from src.tools.search_business import search_local_businesses
from src.tools.search_business_details import get_business_details
from src.tools.review_checking_tool import get_business_reviews

logger = logging.getLogger(__name__)

TARGET_CANDIDATES = 10
ENRICH_LIMIT = 5


# ── Normalization ────────────────────────────────────────────────────────────

def _normalize_business(raw: dict, source: str) -> Optional[RawCandidate]:
    """Map a single local-business-search API result to RawCandidate."""
    name = raw.get("name") or raw.get("title")
    if not name:
        return None

    phones = []
    for key in ("phone_number", "phone"):
        val = raw.get(key)
        if val and val not in phones:
            phones.append(val)

    subtypes = raw.get("subtypes") or raw.get("types") or []

    return RawCandidate(
        name=name,
        phones=phones,
        location=raw.get("full_address") or raw.get("address"),
        service_tags=subtypes if isinstance(subtypes, list) else [subtypes],
        rating=raw.get("rating"),
        website=raw.get("website"),
        business_id=raw.get("business_id") or raw.get("google_id"),
        source=source,
    )


# ── Tier 1 ───────────────────────────────────────────────────────────────────

def _run_local_search(
    query: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    subtypes: Optional[str] = None,
    *,
    relaxed: bool = False,
) -> List[RawCandidate]:
    try:
        params = {
            "query": query,
            "limit": TARGET_CANDIDATES,
            "region": "ng",
            "extract_emails_and_contacts": not relaxed,
        }
        if not relaxed:
            params.update({
                "lat": lat,
                "lng": lng,
                "subtypes": subtypes,
            })

        response = search_local_businesses(**{k: v for k, v in params.items() if v is not None})
        businesses = response.get("data") or response.get("results") or []
        candidates = [_normalize_business(b, "Local Business Search") for b in businesses]
        return [c for c in candidates if c is not None]
    except Exception as e:
        logger.error(f"Local business search failed: {e}")
        return []


def _needs_more_candidates(candidates: List[RawCandidate]) -> bool:
    return len(candidates) < TARGET_CANDIDATES


def _best_candidates(candidates: List[RawCandidate], limit: int = TARGET_CANDIDATES) -> List[RawCandidate]:
    return sorted(
        candidates,
        key=lambda c: (c.completeness_score(), c.rating or 0, c.name.lower()),
        reverse=True,
    )[:limit]


def _merge(base: List[RawCandidate], extra: List[RawCandidate]) -> List[RawCandidate]:
    """Append extra candidates not already present in base (by name)."""
    existing = {c.name.lower() for c in base}
    for c in extra:
        if c.name.lower() not in existing:
            base.append(c)
            existing.add(c.name.lower())
    return base


# ── Tier 2 ───────────────────────────────────────────────────────────────────

def _enrich(candidate: RawCandidate) -> RawCandidate:
    """Run detail + review tools for a candidate that has a business_id."""
    if not candidate.business_id:
        return candidate

    try:
        details = get_business_details.invoke({
            "business_id": candidate.business_id,
            "extract_emails_and_contacts": True,
            "region": "ng",
        })
        if details.get("phone_number") and not candidate.phones:
            candidate.phones = [details["phone_number"]]
        if details.get("email"):
            candidate.email = details["email"]
        if details.get("full_address") and not candidate.location:
            candidate.location = details["full_address"]
        if details.get("subtypes"):
            candidate.service_tags = details["subtypes"]

        level = details.get("price_level")
        if level == 1:
            candidate.price_signal = "LOW"
        elif level == 2:
            candidate.price_signal = "MID"
        elif level and level >= 3:
            candidate.price_signal = "HIGH"
    except Exception as e:
        logger.warning(f"Detail enrichment failed for '{candidate.name}': {e}")

    try:
        reviews = get_business_reviews.invoke({
            "business_id": candidate.business_id,
            "limit": 5,
            "region": "ng",
        })
        review_list = reviews.get("reviews") or []
        snippets = [r.get("review_text", "") for r in review_list[:3] if r.get("review_text")]
        if snippets:
            candidate.reviews_summary = " | ".join(snippets)
    except Exception as e:
        logger.warning(f"Review fetch failed for '{candidate.name}': {e}")

    return candidate


# ── Main node ────────────────────────────────────────────────────────────────

def orchestrate_tools(state: AgentState) -> AgentState:
    intent = state.intent
    logger.info("=" * 60)
    logger.info("NODE 3 | Tool Orchestration")

    # Tier 1: primary search
    logger.info(f"  [Tier 1] Primary search: '{intent.primary_query}'")
    candidates = _run_local_search(
        query=intent.primary_query,
        # lat=intent.primary_lat,
        # lng=intent.primary_lng,
        subtypes=intent.primary_subtypes,
    )
    logger.info(f"  [Tier 1] Primary returned {len(candidates)} candidates")

    if _needs_more_candidates(candidates):
        logger.info(
            f"  [Tier 1] Found fewer than {TARGET_CANDIDATES} candidates — running broader fallback"
        )
        logger.info(f"  [Tier 1] Fallback search: '{intent.fallback_query}'")
        fallback = _run_local_search(
            query="Electrician, Lagos",
            # lat=intent.primary_lat,
            # lng=intent.primary_lng,
            subtypes=intent.fallback_subtypes,
        )
        logger.info(f"  [Tier 1] Fallback returned {len(fallback)} new candidates")
        candidates = _merge(candidates, fallback)

        if _needs_more_candidates(candidates):
            logger.info("  [Tier 1] Still below target — retrying local search with relaxed params")
            relaxed = _run_local_search(intent.fallback_query, relaxed=True)
            logger.info(f"  [Tier 1] Relaxed search returned {len(relaxed)} new candidates")
            candidates = _merge(candidates, relaxed)

        logger.info(f"  [Tier 1] Total after fallback searches: {len(candidates)} candidates")
    else:
        logger.info("  [Tier 1] Candidate target met")

    if not candidates:
        logger.info("  [Tier 1] No candidates found — routing to synthesis with reason: not_found")
        state.synthesis_reason = "not_found"
        logger.info("NODE 3 | Complete")
        return state

    candidates = _best_candidates(candidates, limit=ENRICH_LIMIT)

    # Tier 2: enrich
    logger.info(f"  [Tier 2] Enriching {len(candidates)} candidates via details + reviews tools")
    enriched = []
    for c in candidates:
        if c.business_id:
            logger.info(f"  [Tier 2] Enriching: '{c.name}'")
        enriched.append(_enrich(c))

    state.raw_candidates = enriched
    state.sources = list({c.source for c in state.raw_candidates if c.source})
    logger.info(f"  [Tier 2] Enrichment complete | Sources: {state.sources}")
    logger.info("NODE 3 | Complete")
    return state
