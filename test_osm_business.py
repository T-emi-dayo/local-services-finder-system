# test_search_nigerian_businesses_osm.py
# Quick test script for the search_nigerian_businesses_osm tool.
# Assumes the main module is in the same directory or properly importable.

from src.tools.review_checking_tool import get_business_reviews

# Example usage:
# Replace with actual query and location for testing
query = "0x8082e850673ab39f:0xfd6d3b4bb1dd08aa"
result = get_business_reviews(query)

# Print the result
print(result)