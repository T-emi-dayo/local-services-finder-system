# test_search_nigerian_businesses_osm.py
# Quick test script for the search_nigerian_businesses_osm tool.
# Assumes the main module is in the same directory or properly importable.

from src.tools.osm_tool import search_nigerian_businesses_osm  # Replace 'your_module_name' with the actual filename (e.g., 'osm_business_searcher')

# Sample inputs
service = "pharmacy"
location = "Ikeja, Lagos"
radius_km = 5.0
limit = 10
contact_email = "you@example.com"  # Optional

# Call the function
result = search_nigerian_businesses_osm(
    service=service,
    location=location,
    radius_km=radius_km,
    limit=limit,
    contact_email=contact_email,
)

# Print the result (for quick inspection)
print(result)