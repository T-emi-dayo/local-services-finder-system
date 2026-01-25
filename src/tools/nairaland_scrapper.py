import requests
from bs4 import BeautifulSoup
import time
import random
import re
from typing import List, Optional
from pydantic import BaseModel

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

class NairalandScraperAnti403:
    """
    BeautifulSoup-based scraper for Nairaland with 403 avoidance.
    Rotates User-Agents, uses proxies, randomized delays, sessions.
    Respects robots.txt (check https://www.nairaland.com/robots.txt).
    """

    BASE_URL = "https://www.nairaland.com"
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    ]

    def __init__(self, proxies: Optional[List[str]] = None):
        """
        :param proxies: List of proxy URLs (e.g., ['http://ip:port', 'https://ip:port']) for rotation.
        """
        self.proxies = proxies or []
        self.session = requests.Session()  # Maintains cookies/sessions per guide
        self._update_headers()

    def _update_headers(self):
        """Rotate User-Agent and set Referer per guide."""
        self.session.headers.update({
            "User-Agent": random.choice(self.USER_AGENTS),
            "Referer": self.BASE_URL + "/"  # Mimic coming from homepage
        })

    def _get_proxy(self) -> Optional[dict]:
        """Rotate proxies if provided."""
        if self.proxies:
            proxy = random.choice(self.proxies)
            return {"http": proxy, "https": proxy}
        return None

    def scrape_nairaland(self, query: str, max_results: int = 5, max_pages: int = 1) -> List[ToolResult]:
        """
        Search Nairaland and scrape threads/posts with 403 avoidance.
        Returns List[ToolResult]. Limits depth/pages per guide.
        """
        results = []
        search_url = f"{self.BASE_URL}/search?q={query.replace(' ', '+')}"

        for page in range(max_pages):
            try:
                self._update_headers()  # Rotate headers per request
                proxy = self._get_proxy()
                print(f"Fetching page {page + 1} with proxy: {proxy}")  # Debug

                response = self.session.get(search_url, proxies=proxy, timeout=10)
                response.raise_for_status()

                # Check for CAPTCHA (basic detection per guide)
                if "recaptcha" in response.text.lower() or "captcha" in response.text.lower():
                    return [ToolResult(
                        title="CAPTCHA Detected",
                        url=search_url,
                        snippet="CAPTCHA challenge encountered. Use Selenium or manual solving.",
                        source="nairaland",
                        tool_name="nairaland_scraper_anti403",
                        error="CAPTCHA: Consider 2Captcha or fallback to browser automation."
                    )]

                time.sleep(random.uniform(1, 3))  # Randomized delay per guide

                soup = BeautifulSoup(response.text, "html.parser")
                threads = self._parse_threads(soup, max_results - len(results))

                for thread in threads:
                    if len(results) >= max_results:
                        break
                    thread_result = self._scrape_thread(thread['link'])
                    if thread_result:
                        results.append(thread_result)

                # Pagination: Find "Next" link
                next_link = soup.find("a", text="Next")
                if next_link and 'href' in next_link.attrs:
                    search_url = self.BASE_URL + next_link['href']
                else:
                    break  # No more pages

            except requests.RequestException as e:
                return [ToolResult(
                    title="Request Error",
                    url=search_url,
                    snippet=f"Failed to fetch page: {str(e)}",
                    source="nairaland",
                    tool_name="nairaland_scraper_anti403",
                    error=str(e)
                )]

        if not results:
            return [ToolResult(
                title="No Results",
                url=search_url,
                snippet=f"No threads found for query: {query}",
                source="nairaland",
                tool_name="nairaland_scraper_anti403",
                error="No matching threads."
            )]

        return results

    def _parse_threads(self, soup: BeautifulSoup, limit: int) -> List[dict]:
        """Parse thread links from search/listing page."""
        threads = []
        for a in soup.select("td a")[:limit]:
            href = a.get("href")
            title = a.get_text(strip=True)
            if href and title and href.startswith("/"):
                threads.append({
                    "title": title,
                    "link": self.BASE_URL + href
                })
        return threads

    def _scrape_thread(self, thread_url: str) -> Optional[ToolResult]:
        """Scrape individual thread with anti-403 measures."""
        try:
            self._update_headers()
            proxy = self._get_proxy()
            response = self.session.get(thread_url, proxies=proxy, timeout=10)
            response.raise_for_status()

            if "recaptcha" in response.text.lower():
                return ToolResult(
                    title="Thread CAPTCHA",
                    url=thread_url,
                    snippet="CAPTCHA on thread page.",
                    source="nairaland",
                    tool_name="nairaland_scraper_anti403",
                    error="CAPTCHA detected."
                )

            time.sleep(random.uniform(1, 3))  # Randomized delay

            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.find("title").get_text(strip=True) if soup.find("title") else "Unknown Title"

            posts = []
            authors = []
            content_parts = []

            for table in soup.select("table"):
                user_elem = table.find("a", href=True)
                if user_elem:
                    user = user_elem.get_text(strip=True)
                    post_content = table.get_text(separator="\n").strip()
                    posts.append({"user": user, "content": post_content})
                    authors.append(user)
                    content_parts.append(post_content[:500])

            full_content = "\n\n".join(content_parts)
            snippet = full_content[:200] + "..." if full_content else "No content"

            data_point = {}
            views_match = re.search(r'(\d+) Views', full_content)
            if views_match:
                data_point["views"] = int(views_match.group(1))
            data_point["active_users"] = len(set(authors))
            guests_match = re.search(r'(\d+) guest', full_content)
            if guests_match:
                data_point["guests"] = int(guests_match.group(1))

            return ToolResult(
                title=title,
                url=thread_url,
                snippet=snippet,
                source="nairaland",
                content=full_content,
                authors=authors,
                data_point=data_point,
                confidence=0.8,
                metadata={"posts_count": len(posts)},
                tool_name="nairaland_scraper_anti403"
            )

        except Exception as e:
            return ToolResult(
                title="Thread Scraping Error",
                url=thread_url,
                snippet=f"Failed to scrape thread: {str(e)}",
                source="nairaland",
                tool_name="nairaland_scraper_anti403",
                error=str(e)
            )

# Convenience function
def scrape_nairaland(query: str, max_results: int = 5, max_pages: int = 1, proxies: Optional[List[str]] = None) -> List[ToolResult]:
    """
    Standalone convenience function with 403 avoidance.
    :param proxies: List of proxies for rotation.
    """
    scraper = NairalandScraperAnti403(proxies=proxies)
    return scraper.scrape_nairaland(query, max_results, max_pages)