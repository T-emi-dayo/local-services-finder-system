"""
Tool output schema test.

Calls each tool with a real query and dumps the full raw response
so we can see exactly what fields the API returns before finalising
the normalisation logic in ToolOrchestrationNode.

Run from project root:
    python -m tests.test_tools
"""

import json
import sys
from src.tools.search_business import search_local_businesses
from src.tools.search_business_details import get_business_details
from src.tools.review_checking_tool import get_business_reviews

# ── Config ────────────────────────────────────────────────────────────────────
# Lekki, Lagos coordinates
TEST_QUERY    = "plumber Lekki Lagos"
TEST_LAT      = 6.4698
TEST_LNG      = 3.5852
TEST_SUBTYPES = "Plumber"
TEST_REGION   = "ng"
# ─────────────────────────────────────────────────────────────────────────────


def _print(title: str, data: dict):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print(json.dumps(data, indent=2, default=str))


def test_search_businesses() -> str | None:
    """
    Returns the first business_id found so it can be reused in the
    enrichment tests below.
    """
    print("\n>>> TOOL 1: search_local_businesses")
    print(f"    query='{TEST_QUERY}' | lat={TEST_LAT} | lng={TEST_LNG} | subtypes='{TEST_SUBTYPES}'")

    response = search_local_businesses(
        query=TEST_QUERY,
        lat=TEST_LAT,
        lng=TEST_LNG,
        subtypes=TEST_SUBTYPES,
        region=TEST_REGION,
        limit=3,
        extract_emails_and_contacts=True,
    )

    _print("FULL RESPONSE", response)

    # Try to surface a business_id from wherever the API puts it
    businesses = (
        response.get("data") or
        response.get("results") or
        response.get("businesses") or
        []
    )

    if businesses:
        first = businesses[0]
        print("\n--- First business raw fields ---")
        for k, v in first.items():
            print(f"  {k}: {v!r}")

        business_id = (
            first.get("business_id") or
            first.get("google_id") or
            first.get("place_id")
        )
        print(f"\n>>> Extracted business_id: {business_id!r}")
        return business_id

    print("\n>>> No businesses array found — check top-level keys above")
    return None


def test_business_details(business_id: str):
    print(f"\n>>> TOOL 2: get_business_details (business_id={business_id!r})")

    response = get_business_details.invoke({
        "business_id": business_id,
        "extract_emails_and_contacts": True,
        "region": TEST_REGION,
    })

    _print("FULL RESPONSE", response)

    print("\n--- Top-level keys ---")
    for k, v in response.items():
        print(f"  {k}: {v!r}")


def test_business_reviews(business_id: str):
    print(f"\n>>> TOOL 3: get_business_reviews (business_id={business_id!r})")

    response = get_business_reviews.invoke({
        "business_id": business_id,
        "limit": 3,
        "region": TEST_REGION,
    })

    _print("FULL RESPONSE", response)

    reviews = response.get("reviews") or response.get("data") or []
    if reviews:
        print("\n--- First review raw fields ---")
        for k, v in reviews[0].items():
            print(f"  {k}: {v!r}")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    business_id = test_search_businesses()

    if not business_id:
        print("\n[STOPPED] Cannot run enrichment tests without a business_id.")
        sys.exit(1)

    # test_business_details(business_id)
    # test_business_reviews(business_id)

    print("\n" + "=" * 70)
    print("  All tool tests complete")
    print("=" * 70)
