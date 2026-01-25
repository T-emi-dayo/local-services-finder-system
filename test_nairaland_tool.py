from src.tools.nairaland_tool import query_nairaland_api
from src.tools.nairaland_scrapper import scrape_nairaland # Assuming you have this

# Try API first
results = query_nairaland_api('search_posts', query='Python', per_page=5)
if results and results[0].error:
    print("API failed, using scraper fallback...")
    results = scrape_nairaland("Python programming", max_results=5)

for r in results:
    if r.error:
        print(f"Error: {r.error}")
    else:
        print(f"Title: {r.title}, Snippet: {r.snippet}, Views: {r.data_point.get('pageViews', 'N/A')}")