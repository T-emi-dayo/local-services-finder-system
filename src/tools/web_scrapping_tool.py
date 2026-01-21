import logging
import time
from typing import Optional, Type, Any, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from src.models.ToolResult import ToolResult  # Ensure ToolResult is imported

logger = logging.getLogger(__name__)

# ============================================================================ 
# CONSTANTS 
# ============================================================================

TIMEOUT = 30
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)

# ============================================================================ 
# WEB SCRAPER TOOL 
# ============================================================================

class WebScraperTool:
    """
    Tool for scraping web pages and extracting article content.
    
    Scrapes web pages using BeautifulSoup and returns extracted content
    in ToolResult format.
    """

    def __init__(self):
        """Initialize the web scraper tool."""
        logger.info(f"✅ Web Scraper Tool initialized")
        logger.info(f"   User-Agent: {DEFAULT_USER_AGENT[:50]}...")

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a web page."""
        if not url or not url.strip():
            raise ValueError("URL cannot be empty")
        
        try:
            response = requests.get(url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch page: {e}")
            return None

    def _parse_page(self, html: str, url: str) -> Optional[dict]:
        """Parse HTML and extract article content."""
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text() if soup.title else "No title found"
        content = soup.get_text()
        return {
            "title": title,
            "content": content[:5000],  # Limit to first 5000 characters
            "url": url,
            "source": urlparse(url).netloc
        }

    def _convert_to_tool_result(self, page_data: dict) -> ToolResult:
        """Convert page data dict to ToolResult object."""
        return ToolResult(
            title=page_data.get("title", "No title"),
            url=page_data.get("url", ""),
            snippet=page_data.get("content", "")[:500],
            source=page_data.get("source", "web"),
            content=page_data.get("content", ""),
            metadata={"domain": page_data.get("source", ""), "full_url": page_data.get("url", "")}
        )

    def scrape(self, url: str) -> Optional[ToolResult]:
        """Scrape a web page and return content in ToolResult format."""
        html = self._fetch_page(url)
        if html:
            page_data = self._parse_page(html, url)
            return self._convert_to_tool_result(page_data)
        return None

# ============================================================================ 
# CONVENIENCE FUNCTION 
# ============================================================================

@tool
def scrape_web(url: str) -> Optional[ToolResult]:
    """Convenience function to scrape a web page and return ToolResult instance."""
    tool = WebScraperTool()
    return tool.scrape(url)
