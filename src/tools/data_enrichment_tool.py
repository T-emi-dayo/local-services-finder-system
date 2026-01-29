from __future__ import annotations

import math
import time
import random
from typing import Any, Dict, List, Optional, Tuple
import requests
from langchain.tools import tool

# ============================================================
# SETTINGS (keys, endpoints, tuning knobs)
# ============================================================

GOOGLE_PLACES_API_KEY = "PUT_YOUR_KEY_HERE"

# Places API (New) endpoints
GOOGLE_PLACES_SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"   # POST
GOOGLE_PLACES_DETAILS_URL_TMPL = "https://places.googleapis.com/v1/places/{place_id}" # GET

# Rate limiting + retries (tune to your quota and latency tolerance)
MIN_INTERVAL_S = 0.10
TIMEOUT_S = 20.0
MAX_RETRIES = 4
BACKOFF_BASE_S = 0.4
BACKOFF_JITTER_S = 0.2

# Match behavior
SEARCH_RADIUS_M = 300            # location bias radius (approx)
SEARCH_MAX_CANDIDATES = 8        # how many Google candidates we’ll score
MATCH_MIN_SCORE = 0.55           # below this => treat as "unmatched"

# Field masks (keep these lean for cost control; FieldMask is required)
# NOTE: "places.*" masks are for search results; for details we use the place fields directly.
SEARCH_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.location,places.types"

DETAILS_FIELD_MASK = ",".join([
    "id",
    "displayName",
    "formattedAddress",
    "location",
    "rating",
    "userRatingCount",
    "nationalPhoneNumber",
    "internationalPhoneNumber",
    "websiteUri",
    "googleMapsUri",
    "regularOpeningHours",
    "types",
])

# Optional: in-memory cache (swap with Redis in real production)
CACHE_ENABLED = True
_CACHE: Dict[str, Any] = {}

# Identify your app (good practice; Google likes consistent UA)
USER_AGENT = "YourAppName/1.0 (+contact@yourdomain.com)"


# ============================================================
# Small utilities
# ============================================================

_last_call_ts = 0.0

def _sleep_rate_limit():
    global _last_call_ts
    now = time.time()
    wait_s = (_last_call_ts + MIN_INTERVAL_S) - now
    if wait_s > 0:
        time.sleep(wait_s)
    _last_call_ts = time.time()

def _backoff(attempt: int):
    time.sleep((BACKOFF_BASE_S * (2 ** attempt)) + random.uniform(0, BACKOFF_JITTER_S))

def _norm(s: Optional[str]) -> str:
    return " ".join((s or "").strip().lower().split())

def _lev_ratio(a: str, b: str) -> float:
    """
    Lightweight similarity without extra deps.
    Token-based Jaccard + prefix bonus. Not perfect, but stable.
    """
    a_n, b_n = _norm(a), _norm(b)
    if not a_n or not b_n:
        return 0.0
    a_t, b_t = set(a_n.split()), set(b_n.split())
    j = len(a_t & b_t) / max(1, len(a_t | b_t))
    prefix = 0.15 if (a_n[:10] == b_n[:10]) else 0.0
    return min(1.0, j + prefix)

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def _dist_score(meters: float) -> float:
    # 1.0 at 0m, decays to ~0.0 past ~1km
    return math.exp(-meters / 350.0)

def _cache_get(k: str) -> Any:
    return _CACHE.get(k) if CACHE_ENABLED else None

def _cache_set(k: str, v: Any):
    if CACHE_ENABLED:
        _CACHE[k] = v


# ============================================================
# HTTP client (Google Places API New)
# ============================================================

def _google_request(method: str, url: str, *, headers: Dict[str, str], json_body: Any = None) -> Any:
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            _sleep_rate_limit()
            resp = requests.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=TIMEOUT_S,
            )
            # Handle common throttles/transients
            if resp.status_code in (429, 500, 503, 504):
                raise requests.HTTPError(f"{resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            if attempt >= MAX_RETRIES:
                break
            _backoff(attempt)
    raise RuntimeError(f"Google request failed: {method} {url}") from last_err


def google_search_text(query: str, *, lat: float, lon: float, radius_m: int = SEARCH_RADIUS_M) -> List[Dict[str, Any]]:
    """
    Calls Places API (New) Text Search: POST /v1/places:searchText
    Uses location bias around (lat, lon) to keep matches local.
    """
    cache_key = f"g_search::{query}::{lat:.5f},{lon:.5f}::{radius_m}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    headers = {
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": SEARCH_FIELD_MASK,  # FieldMask controls response + billing
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    body = {
        "textQuery": query,
        "maxResultCount": SEARCH_MAX_CANDIDATES,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": float(radius_m),
            }
        },
        # Helpful when you mainly want Nigeria results:
        "regionCode": "NG",
        "languageCode": "en",
    }

    data = _google_request("POST", GOOGLE_PLACES_SEARCH_TEXT_URL, headers=headers, json_body=body)
    places = data.get("places", []) or []
    _cache_set(cache_key, places)
    return places


def google_place_details(place_id: str) -> Dict[str, Any]:
    """
    Calls Place Details (New): GET /v1/places/{place_id}
    """
    cache_key = f"g_details::{place_id}::{DETAILS_FIELD_MASK}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    headers = {
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": DETAILS_FIELD_MASK,  # required
        "User-Agent": USER_AGENT,
    }

    url = GOOGLE_PLACES_DETAILS_URL_TMPL.format(place_id=place_id)
    data = _google_request("GET", url, headers=headers)
    _cache_set(cache_key, data)
    return data


# ============================================================
# Matching + enrichment
# ============================================================

def _extract_google_candidate(candidate: Dict[str, Any]) -> Tuple[str, str, float, float]:
    place_id = candidate.get("id", "")
    name = (((candidate.get("displayName") or {}).get("text")) or "")
    loc = candidate.get("location") or {}
    return place_id, name, float(loc.get("latitude", 0.0)), float(loc.get("longitude", 0.0))

def match_osm_to_google(
    osm_place: Dict[str, Any],
    *,
    query_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    For one OSM result, find best Google place match and return details.
    Returns:
      {matched: bool, score: float, place_id: str|None, details: dict|None, debug: {...}}
    """
    osm_name = osm_place.get("name") or ""
    lat = osm_place.get("lat")
    lon = osm_place.get("lon")
    if lat is None or lon is None:
        return {"matched": False, "score": 0.0, "place_id": None, "details": None, "debug": {"reason": "missing_latlon"}}

    # Query: try name + optional service hint
    q = osm_name
    if query_hint:
        q = f"{osm_name} {query_hint}".strip()

    candidates = google_search_text(q, lat=float(lat), lon=float(lon))

    best = {"score": 0.0, "place_id": None, "candidate": None, "dist_m": None, "name_sim": 0.0}

    for c in candidates:
        pid, gname, glat, glon = _extract_google_candidate(c)
        if not pid or not glat or not glon:
            continue

        dist_m = _haversine_m(float(lat), float(lon), glat, glon)
        name_sim = _lev_ratio(osm_name, gname)

        # Weighted score: name similarity dominates, distance helps disambiguate
        score = (0.70 * name_sim) + (0.30 * _dist_score(dist_m))

        if score > best["score"]:
            best.update({"score": score, "place_id": pid, "candidate": c, "dist_m": dist_m, "name_sim": name_sim})

    if best["place_id"] is None or best["score"] < MATCH_MIN_SCORE:
        return {
            "matched": False,
            "score": float(best["score"]),
            "place_id": None,
            "details": None,
            "debug": {"candidates": len(candidates), "best_name_sim": best["name_sim"], "best_dist_m": best["dist_m"]},
        }

    details = google_place_details(best["place_id"])
    return {
        "matched": True,
        "score": float(best["score"]),
        "place_id": best["place_id"],
        "details": details,
        "debug": {"candidates": len(candidates), "best_name_sim": best["name_sim"], "best_dist_m": best["dist_m"]},
    }


@tool
def enrich_data(
    osm_results: List[Dict[str, Any]],
    *,
    service_hint: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Enrich OSM place data with Google Places details for an LLM agent.

    This tool takes a list of OSM (OpenStreetMap) place records and attempts to match each one to a corresponding Google Place using the Google Places API (New). For matched places, it retrieves additional details like ratings, contact info, and opening hours.

    Args:
        osm_results (List[Dict[str, Any]]): A list of dictionaries, each representing an OSM place. Each dict must include at least 'name', 'lat', and 'lon' keys (e.g., [{'name': 'Example Cafe', 'lat': 6.5244, 'lon': 3.3792, ...}]).
        service_hint (Optional[str]): An optional string to append to the search query for better matching (e.g., 'restaurant' or 'hotel'). Defaults to None.
        limit (Optional[int]): An optional integer to limit the number of OSM results processed. Defaults to None (process all).

    Returns:
        Dict[str, Any]: A dictionary with:
            - 'meta': Metadata about the enrichment process (provider, field masks, match threshold).
            - 'results': A list of enriched OSM records. Each record is the original OSM data plus a 'google' key containing match info and Google details if matched.

    Example usage in an LLM agent:
        Input: [{"name": "Lagos Central Mosque", "lat": 6.4549, "lon": 3.4246}]
        Output: {"meta": {...}, "results": [{"name": "Lagos Central Mosque", "lat": 6.4549, "lon": 3.4246, "google": {"matched": True, "match_score": 0.85, "place_id": "...", "rating": 4.5, ...}}]}

    Notes:
        - Requires a valid GOOGLE_PLACES_API_KEY.
        - Matching is based on name similarity and proximity; not all OSM places will match.
        - Rate limiting and caching are applied to respect API quotas.
        - If no match, 'google' will include 'matched': False and debug info.
    """
    if limit is not None:
        osm_results = osm_results[:int(limit)]

    enriched = []
    for p in osm_results:
        m = match_osm_to_google(p, query_hint=service_hint)
        out = dict(p)  # copy original OSM record
        out["google"] = {
            "matched": m["matched"],
            "match_score": m["score"],
            "place_id": m["place_id"],
        }
        if m["matched"] and m["details"]:
            d = m["details"]
            dn = ((d.get("displayName") or {}).get("text")) if isinstance(d.get("displayName"), dict) else d.get("displayName")

            out["google"].update({
                "name": dn,
                "formatted_address": d.get("formattedAddress"),
                "lat": (d.get("location") or {}).get("latitude"),
                "lon": (d.get("location") or {}).get("longitude"),
                "rating": d.get("rating"),
                "user_rating_count": d.get("userRatingCount"),
                "website": d.get("websiteUri"),
                "maps_url": d.get("googleMapsUri"),
                "phone_national": d.get("nationalPhoneNumber"),
                "phone_international": d.get("internationalPhoneNumber"),
                "opening_hours": d.get("regularOpeningHours"),
                "types": d.get("types"),
            })
        else:
            out["google"].update({"debug": m.get("debug")})

        enriched.append(out)

    return {
        "meta": {
            "provider": "google_places_new",
            "search_field_mask": SEARCH_FIELD_MASK,
            "details_field_mask": DETAILS_FIELD_MASK,
            "match_min_score": MATCH_MIN_SCORE,
        },
        "results": enriched,
    }