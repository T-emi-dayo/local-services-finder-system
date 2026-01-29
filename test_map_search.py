# test_enrich_data.py
# Quick test script for the enrich_data tool.
# Assumes the main module is in the same directory or properly importable.
# Replace 'PUT_YOUR_KEY_HERE' with a real Google Places API key in the main module before running.

from src.tools.data_enrichment_tool import enrich_data  # Replace 'your_module_name' with the actual filename (e.g., 'google_places_enricher')

# Sample OSM results (e.g., places in Lagos, Nigeria)
osm_results = [
    {
        "name": "Lagos Central Mosque",
        "lat": 6.4549,
        "lon": 3.4246,
        "osm_id": 12345,  # Optional extra fields
    },
    {
        "name": "Eko Hotel & Suites",
        "lat": 6.4474,
        "lon": 3.4223,
        "osm_id": 67890,
    }
]

# Call the function with optional parameters
result = enrich_data(
    osm_results=osm_results,
    service_hint="hotel",  # Optional: helps with matching for the second place
    limit=2  # Optional: limit to 2 results
)

# Print the result (for quick inspection)
print(result)