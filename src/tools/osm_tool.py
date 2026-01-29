from __future__ import annotations

import json
import time
import random
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ----------------------------
# Configuration / Defaults
# ----------------------------

DEFAULT_OVERPASS_ENDPOINTS = [
    # Official-ish public instance
    "https://overpass-api.de/api/interpreter",
    # Community-run instance (often reliable)
    "https://overpass.private.coffee/api/interpreter",
]

DEFAULT_NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"


@dataclass
class OSMToolConfig:
    user_agent: str
    contact_email: Optional[str] = None

    # Public Nominatim policy says: max 1 req/sec, unique UA (no default library UA).
    nominatim_min_interval_s: float = 1.05

    # Overpass: keep polite; actual limits vary by instance.
    overpass_min_interval_s: float = 0.30

    # HTTP behavior
    timeout_s: float = 30.0
    max_retries: int = 4
    backoff_base_s: float = 0.6
    backoff_jitter_s: float = 0.25

    # Safety caps
    max_radius_km: float = 50.0
    max_results: int = 50


class RateLimiter:
    """Simple per-host rate limiter."""
    def __init__(self):
        self._last: Dict[str, float] = {}

    def wait(self, key: str, min_interval_s: float):
        now = time.time()
        last = self._last.get(key, 0.0)
        wait_s = (last + min_interval_s) - now
        if wait_s > 0:
            time.sleep(wait_s)
        self._last[key] = time.time()


class HTTPClient:
    def __init__(self, cfg: OSMToolConfig):
        self.cfg = cfg
        self.session = requests.Session()
        self.ratelimiter = RateLimiter()

    def _headers(self) -> Dict[str, str]:
        # Nominatim explicitly requires a valid UA identifying your app.
        # Include email either in UA or as a parameter (some clients do). Keeping UA simple:
        ua = self.cfg.user_agent
        if self.cfg.contact_email and self.cfg.contact_email not in ua:
            ua = f"{ua} ({self.cfg.contact_email})"
        return {"User-Agent": ua, "Accept": "application/json"}

def request_json(self, method: str, url: str, *, params=None, data=None,
                 min_interval_key=None, min_interval_s=0.0) -> Any:
    headers = self._headers()
    last_err = None

    for attempt in range(self.cfg.max_retries + 1):
        # ✅ Apply rate limit BEFORE EACH attempt (including retries)
        if min_interval_key:
            self.ratelimiter.wait(min_interval_key, min_interval_s)

        try:
            resp = self.session.request(
                method,
                url,
                params=params,
                data=data,
                headers=headers,
                timeout=self.cfg.timeout_s,
            )

            # Handle common throttle responses
            if resp.status_code in (429, 503, 504):
                # ✅ Respect Retry-After if present (seconds)
                ra = resp.headers.get("Retry-After")
                if ra:
                    try:
                        time.sleep(max(0.0, float(ra)))
                    except ValueError:
                        pass
                raise requests.HTTPError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}",
                    response=resp
                )

            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            last_err = e
            if attempt >= self.cfg.max_retries:
                break
            backoff = (self.cfg.backoff_base_s * (2 ** attempt)) + random.uniform(0, self.cfg.backoff_jitter_s)
            time.sleep(backoff)

    raise RuntimeError(f"Request failed after retries: {url}") from last_err



# ----------------------------
# Domain helpers
# ----------------------------

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).lower()


def infer_osm_tag_filters(service_query: str) -> List[Tuple[str, str]]:
    """
    Minimal heuristic mapping from "service" query to OSM tags.
    Production usage: replace with a proper taxonomy mapping table.

    You can expand this aggressively for your product categories.
    """
    q = normalize_text(service_query)

    # Examples: you should customize.
    if any(k in q for k in ["pharmacy", "chemist"]):
        return [("amenity", "pharmacy")]
    if any(k in q for k in ["hospital", "clinic", "health centre", "health center"]):
        return [("amenity", "hospital"), ("amenity", "clinic")]
    if any(k in q for k in ["restaurant", "eatery", "food"]):
        return [("amenity", "restaurant"), ("amenity", "fast_food"), ("amenity", "cafe")]
    if any(k in q for k in ["hotel", "lodging"]):
        return [("tourism", "hotel"), ("tourism", "guest_house"), ("tourism", "hostel")]
    if any(k in q for k in ["lawyer", "law firm", "legal"]):
        return [("office", "lawyer")]
    if any(k in q for k in ["bank", "atm"]):
        return [("amenity", "bank"), ("amenity", "atm")]
    if any(k in q for k in ["supermarket", "grocery"]):
        return [("shop", "supermarket"), ("shop", "convenience")]

    # Default fallback: try matching by name/operator contains query (less precise).
    # We'll implement this later using regex on "name" tags.
    return []


def build_overpass_query(
    lat: float,
    lon: float,
    radius_m: int,
    *,
    tag_filters: List[Tuple[str, str]],
    text_fallback: Optional[str],
    limit: int,
    timeout_s: int = 25,
) -> str:
    """
    Overpass QL query.
    Overpass supports find-by-tags and spatial filters.
    """
    # Safety: Overpass limit is best-effort; we can also truncate client-side.
    lim = max(1, min(limit, 500))

    parts = [f'[out:json][timeout:{timeout_s}];(']

    if tag_filters:
        for k, v in tag_filters:
            # nwr = node/way/relation
            parts.append(f'nwr["{k}"="{v}"](around:{radius_m},{lat},{lon});')
    else:
        # Text fallback: match name-like fields with regex (can be expensive).
        # Keep it tight; anchor loosely with word boundaries for better precision.
        if text_fallback:
            t = re.escape(text_fallback.strip())
            # Use word boundaries to avoid partial matches
            parts.append(f'nwr["name"~"(?i)\\b{t}\\b"](around:{radius_m},{lat},{lon});')
            parts.append(f'nwr["brand"~"(?i)\\b{t}\\b"](around:{radius_m},{lat},{lon});')
            parts.append(f'nwr["operator"~"(?i)\\b{t}\\b"](around:{radius_m},{lat},{lon});')

    parts.append(');')
    # "out center" gives centroid for ways/relations; "tags" include business info.
    parts.append('out tags center;')
    return "\n".join(parts)


def extract_osm_results(overpass_json: Dict[str, Any], *, hard_limit: int) -> List[Dict[str, Any]]:
    elements = overpass_json.get("elements", [])
    out = []

    for el in elements:
        if not isinstance(el, dict):
            continue  # Skip invalid elements
        tags = el.get("tags", {}) or {}
        # location
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            center = el.get("center") or {}
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            continue  # Skip if no location

        out.append({
            "osm_type": el.get("type"),
            "osm_id": el.get("id"),
            "name": tags.get("name"),
            "tags": tags,
            "lat": lat,
            "lon": lon,
            "address": {
                "housenumber": tags.get("addr:housenumber"),
                "street": tags.get("addr:street"),
                "city": tags.get("addr:city"),
                "state": tags.get("addr:state"),
                "postcode": tags.get("addr:postcode"),
            },
            "contact": {
                "phone": tags.get("phone") or tags.get("contact:phone"),
                "website": tags.get("website") or tags.get("contact:website"),
                "email": tags.get("email") or tags.get("contact:email"),
            },
            "category": {
                "amenity": tags.get("amenity"),
                "shop": tags.get("shop"),
                "office": tags.get("office"),
                "tourism": tags.get("tourism"),
                "craft": tags.get("craft"),
            }
        })

    # Truncate (Overpass doesn't guarantee order)
    return out[:hard_limit]


# ----------------------------
# Core clients
# ----------------------------

class NominatimClient:
    def __init__(self, http: HTTPClient, endpoint: str = DEFAULT_NOMINATIM_ENDPOINT):
        self.http = http
        self.endpoint = endpoint

    def geocode_ng(self, query: str, *, limit: int = 1) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 40))
        
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": str(limit),
            "countrycodes": "ng",
        }
        # Some deployments accept "email" parameter; usage policy emphasizes UA identification.
        if self.http.cfg.contact_email:
            params["email"] = self.http.cfg.contact_email

        return self.http.request_json(
            "GET",
            self.endpoint,
            params=params,
            min_interval_key="nominatim",
            min_interval_s=self.http.cfg.nominatim_min_interval_s,
        )


class OverpassClient:
    def __init__(self, http: HTTPClient, endpoints: List[str] = None):
        self.http = http
        self.endpoints = endpoints or list(DEFAULT_OVERPASS_ENDPOINTS)

    def query(self, ql: str) -> Dict[str, Any]:
        # POST is preferred for longer queries
        last_err = None
        for url in self.endpoints:
            try:
                return self.http.request_json(
                    "POST",
                    url,
                    data=ql.encode("utf-8"),
                    min_interval_key=f"overpass:{url}",
                    min_interval_s=self.http.cfg.overpass_min_interval_s,
                )
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError("All Overpass endpoints failed") from last_err


# ----------------------------
# Agent-facing tool function
# ----------------------------

class SearchBusinessInput(BaseModel):
    """Input schema for searching Nigerian businesses on OpenStreetMap."""
    service: str = Field(
        description="The type of service or business to search for (e.g., 'pharmacy', 'hotel', 'restaurant', 'plumber', 'lawyer')"
    )
    location: str = Field(
        description="A location string in Nigeria (e.g., 'Gwarimpa, Abuja', 'Ikeja, Lagos', 'Wuse 2, Abuja')"
    )
    radius_km: float = Field(
        default=5.0,
        description="Search radius in kilometers around the location (0.2-50.0 km). Default is 5.0 km"
    )
    limit: int = Field(
        default=20,
        description="Maximum number of results to return (1-50). Default is 20"
    )

@ tool(args_schema=SearchBusinessInput)
def search_nigerian_businesses_osm(
    service: str,
    location: str,
    *,
    radius_km: float = 5.0,
    limit: int = 20,
    user_agent: str = "YourAppName/1.0 (contact: you@example.com)",
    contact_email: Optional[str] = None,
    overpass_endpoints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Search for businesses or services in Nigeria using OpenStreetMap (OSM) data.

    This tool geocodes a location in Nigeria via Nominatim, then queries Overpass API for nearby OSM places matching the service type. It's useful for finding local businesses like pharmacies, hotels, or restaurants based on OSM tags and text matching.

    Args:
        service (str): The type of service or business to search for (e.g., "pharmacy", "hotel", "restaurant"). Supports heuristic tag mapping; falls back to text search if no tags match.
        location (str): A location string in Nigeria (e.g., "Ikeja, Lagos" or "Wuse 2, Abuja"). Must be geocodable by Nominatim.
        radius_km (float, optional): Search radius in kilometers around the geocoded location. Defaults to 5.0 (clamped to 0.2-50.0 km).
        limit (int, optional): Maximum number of results to return. Defaults to 20 (clamped to 1-50).
        user_agent (str, optional): A unique user agent string for API requests (required by Nominatim policy). Defaults to a placeholder; customize with your app name and contact.
        contact_email (str, optional): Contact email for API requests (helps with Nominatim compliance). Defaults to None.
        overpass_endpoints (List[str], optional): Custom Overpass API endpoints. Defaults to public instances.

    Returns:
        Dict[str, Any]: A structured dictionary with:
            - 'query': Echo of input parameters.
            - 'geocode': Geocoded location details (or None if not found).
            - 'results': List of OSM places, each with keys like 'name', 'lat', 'lon', 'address', 'contact', 'category', etc.
            - 'meta': Metadata including status, used filters, and notes.

    Example usage in an LLM agent:
        Input: service="pharmacy", location="Ikeja, Lagos", radius_km=10.0, limit=5
        Output: {"query": {...}, "geocode": {"display_name": "Ikeja, Lagos, Nigeria", "lat": 6.6018, "lon": 3.3515, ...}, "results": [{"name": "Example Pharmacy", "lat": 6.602, "lon": 3.352, ...}], "meta": {"status": "ok", ...}}

    Notes:
        - Requires internet access for API calls.
        - Respect rate limits: Nominatim (≤1 req/sec), Overpass (varies).
        - OSM data may be incomplete; consider fallbacks for critical use.
        - If location isn't found, 'geocode' will be None and 'results' empty.
        - Customize `infer_osm_tag_filters` for better service matching.
    """
    if not service or not location:
        raise ValueError("Service and location are required.")

    cfg = OSMToolConfig(
        user_agent=user_agent,
        contact_email=contact_email,
        max_results=limit,
        max_radius_km=max(1.0, radius_km),
    )
    http = HTTPClient(cfg)
    nom = NominatimClient(http)
    ov = OverpassClient(http, endpoints=overpass_endpoints or DEFAULT_OVERPASS_ENDPOINTS)

    radius_km = clamp(float(radius_km), 0.2, cfg.max_radius_km)
    limit = int(clamp(int(limit), 1, cfg.max_results))

    # 1) Geocode in Nigeria
    geo = nom.geocode_ng(location, limit=1)
    if not geo:
        return {
            "query": {"service": service, "location": location, "radius_km": radius_km, "limit": limit},
            "geocode": None,
            "results": [],
            "meta": {"status": "no_geocode", "note": "Location not found in Nigeria via Nominatim"},
        }

    g = geo[0]
    lat, lon = float(g["lat"]), float(g["lon"])

    # 2) Build Overpass query
    tag_filters = infer_osm_tag_filters(service)
    ql = build_overpass_query(
        lat, lon, int(radius_km * 1000),
        tag_filters=tag_filters,
        text_fallback=None if tag_filters else service,
        limit=limit,
        timeout_s=25,
    )

    # 3) Query Overpass
    data = ov.query(ql)
    results = extract_osm_results(data, hard_limit=limit)

    return {
        "query": {"service": service, "location": location, "radius_km": radius_km, "limit": limit},
        "geocode": {
            "display_name": g.get("display_name"),
            "lat": lat,
            "lon": lon,
            "type": g.get("type"),
            "class": g.get("class"),
        },
        "results": results,
        "meta": {
            "status": "ok",
            "overpass_endpoints": ov.endpoints,
            "used_tag_filters": tag_filters,
            "notes": [
                "OSM coverage varies by area/category; consider adding provider fallbacks for completeness.",
                "Respect Nominatim public policy (<= 1 req/sec).",
            ],
        },
    }