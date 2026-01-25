from src.tools.map_search_tool import search_location

# Test without key (OSM)
results = search_location("Seismic Consulting Limited")
print("Results:", results)
for r in results:
    print(f"Title: {r.title}, Error: {r.error}")

# Test with key (if you have one)
# results = search_location("Eiffel Tower", api_key="YOUR_KEY")