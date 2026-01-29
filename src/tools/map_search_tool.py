import os
from typing import List, Dict, Optional
from pydantic import BaseModel
from langchain.tools import tool

try:
    import googlemaps
except ImportError:
    googlemaps = None  # Fallback if not installed

try:
    from geopy.geocoders import Nominatim
except ImportError:
    Nominatim = None  # Fallback if not installed

class ToolResult(BaseModel):
    """Result from a tool (search, API, scraping, etc.)."""
    
    # Core fields (used by all tools)
    title: str                         # Source title / data name
    url: str                           # Source URL / API endpoint
    snippet: str                       # Brief excerpt or summary
    source: str                        # Tool name: "pubmed", "market_price_tool", "web", etc.
    date: Optional[str] = None         # Publication/data date
    
    # Text-focused fields (healthcare, news, web scraping)
    content: Optional[str] = None      # Full content (populated after scraping)
    authors: Optional[List[str]] = None  # Authors if available
    
    # Structured data fields (finance, APIs, metrics)
    data_point: Optional[dict] = None  # Structured data: {"price": 150.25, "volume": 1M, ...}
    confidence: Optional[float] = None # Data confidence (0-1)
    
    # Metadata and tracking
    metadata: dict = {}                # Tool-specific data
    tool_name: Optional[str] = None    # Which tool returned this
    
    # Error Handling
    error: Optional[str] = None        # Error message if tool failed

class IntelligentMapSearch:
    """
    An intelligent map search tool that uses Google Maps if an API key is provided,
    falling back to OpenStreetMap via geopy. Based on official library docs:
    - googlemaps: https://googlemaps.github.io/google-maps-services-python/docs/
    - geopy: https://geopy.readthedocs.io/en/stable/
    """

    def __init__(self, google_api_key: Optional[str] = None):
        """
        Initialize the search tool.
        :param google_api_key: Google Maps API key (optional). If None or invalid, uses OSM fallback.
        """
        self.google_api_key = google_api_key or os.getenv('GOOGLE_MAPS_API_KEY')
        self.use_google = bool(self.google_api_key and googlemaps)
        if self.use_google:
            self.gmaps_client = googlemaps.Client(key=self.google_api_key)
        else:
            self.geolocator = Nominatim(user_agent="intelligent-map-search-agent") if Nominatim else None

    def search_location(self, query: str, max_results: int = 5) -> List[ToolResult]:
        """
        Convenience function for agents: Search for locations based on a query.
        Returns a list of ToolResult objects with location data.
        Automatically uses Google Maps if key is available, else OSM.

        :param query: Search query (e.g., "restaurants in New York").
        :param max_results: Max results to return (default 5).
        :return: List of ToolResult objects. If no results, returns a single ToolResult with error.
        """
        print(f"Using Google: {self.use_google}")  # Debug
        if self.use_google:
            print("Calling Google search")  # Debug
            return self._search_google(query, max_results)
        elif self.geolocator:
            print("Calling OSM search")  # Debug
            return self._search_osm(query, max_results)
        else:
            print("No provider available")  # Debug
            return [ToolResult(
                title="Search Failed",
                url="",
                snippet="No valid search provider available.",
                source="intelligent_map_search",
                tool_name="intelligent_map_search",
                error="Install googlemaps or geopy libraries."
            )]

    def _search_google(self, query: str, max_results: int) -> List[ToolResult]:
        """
        Search using Google Maps Places API (per googlemaps docs).
        """
        try:
            results = self.gmaps_client.places(query=query)
            places = results.get('results', [])[:max_results]
            if not places:
                return [ToolResult(
                    title="No Results",
                    url="",
                    snippet=f"No locations found for query: {query}",
                    source="google_maps",
                    tool_name="intelligent_map_search",
                    error="No results from Google Maps."
                )]
            return [
                ToolResult(
                    title=place.get('name', 'Unknown Place'),
                    url=f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id', '')}",
                    snippet=place.get('formatted_address', 'No address available'),
                    source="google_maps",
                    data_point={
                        "lat": place['geometry']['location']['lat'],
                        "lng": place['geometry']['location']['lng'],
                        "rating": place.get('rating'),
                        "types": place.get('types', [])
                    },
                    confidence=0.9 if place.get('rating') else 0.7,  # Higher if rated
                    metadata={"place_id": place.get('place_id')},
                    tool_name="intelligent_map_search"
                )
                for place in places
            ]
        except Exception as e:
            return [ToolResult(
                title="Search Error",
                url="",
                snippet=f"Error searching Google Maps: {str(e)}",
                source="google_maps",
                tool_name="intelligent_map_search",
                error=str(e)
            )]

    def _search_osm(self, query: str, max_results: int) -> List[ToolResult]:
        """
        Search using OpenStreetMap via geopy Nominatim (per geopy docs).
        """
        try:
            locations = self.geolocator.geocode(query, exactly_one=False, limit=max_results)
            if not locations:
                return [ToolResult(
                    title="No Results",
                    url="",
                    snippet=f"No locations found for query: {query}",
                    source="openstreetmap",
                    tool_name="intelligent_map_search",
                    error="No results from OpenStreetMap."
                )]
            return [
                ToolResult(
                    title=location.address.split(',')[0] if location.address else 'Unknown Place',
                    url=f"https://www.openstreetmap.org/?mlat={location.latitude}&mlon={location.longitude}&zoom=15",
                    snippet=location.address or 'No address available',
                    source="openstreetmap",
                    data_point={
                        "lat": location.latitude,
                        "lng": location.longitude
                    },
                    confidence=0.6,  # Lower confidence for OSM
                    metadata={"raw_address": location.raw.get('display_name', '')},
                    tool_name="intelligent_map_search"
                )
                for location in locations
            ]
        except Exception as e:
            return [ToolResult(
                title="Search Error",
                url="",
                snippet=f"Error searching OpenStreetMap: {str(e)}",
                source="openstreetmap",
                tool_name="intelligent_map_search",
                error=str(e)
            )]

# Convenience function alias for easy agent use
@ tool
def search_location(query: str, api_key: Optional[str] = None, max_results: int = 5) -> List[ToolResult]:
    """
    Standalone convenience function. Initializes the tool and performs search.
    Ideal for agents: just call this with a query. Returns List[ToolResult].
    """
    tool = IntelligentMapSearch(google_api_key=api_key)
    return tool.search_location(query, max_results)