from src.tools.nairaland_scrapper import scrape_nairaland

results = scrape_nairaland("politics in Nigeria")
for result in results:
    print(f"Title: {result.title}")
    print(f"Snippet: {result.snippet}")
    print(f"Content: {result.content[:100] if result.content else 'N/A'}")
    if result.error:
        print(f"Error: {result.error}")