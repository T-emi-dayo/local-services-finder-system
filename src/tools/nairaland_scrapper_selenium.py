from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import time
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

class SeleniumNairalandScraper:
    """
    Selenium-based scraper for Nairaland. Handles dynamic content.
    Based on Selenium docs: https://www.selenium.dev/documentation/
    """

    BASE_URL = "https://www.nairaland.com"

    def __init__(self, driver_path: Optional[str] = None, proxy: Optional[str] = None, headless: bool = True):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
        
        # Try Selenium Manager first (auto-manages drivers in Selenium 4.11+)
        try:
            self.driver = webdriver.Chrome(options=options)  # No service needed
            print("Using Selenium Manager for driver.")
        except Exception as e:
            print(f"Selenium Manager failed: {e}")
            if not driver_path:
                raise ValueError("Driver path required if Selenium Manager fails. Download from https://chromedriver.chromium.org/downloads")
            from selenium.webdriver.chrome.service import Service
            service = Service(executable_path=driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)

    def scrape_nairaland(self, query: str, max_results: int = 5) -> List[ToolResult]:
        """
        Search Nairaland and scrape threads. Returns List[ToolResult].
        """
        try:
            # Direct navigation to search URL (simpler than form submission)
            search_url = f"{self.BASE_URL}/search?q={query.replace(' ', '+')}"
            print(f"Navigating to search URL: {search_url}")  # Debug
            self.driver.get(search_url)
            time.sleep(3)  # Wait for page load
            print(f"Current URL after load: {self.driver.current_url}")  # Debug: Check if redirected

            # Check if page loaded (basic check)
            if "search" not in self.driver.current_url:
                raise WebDriverException("Search page did not load correctly.")

            # Find thread links on search results page
            try:
                thread_links = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '/topic-')]"))
                )[:max_results]
                print(f"Found {len(thread_links)} thread links.")  # Debug
            except TimeoutException:
                print("Timeout: No thread links found on search page.")
                self.driver.quit()
                return [ToolResult(
                    title="No Results",
                    url=search_url,
                    snippet=f"No threads found for query: {query}",
                    source="nairaland",
                    tool_name="selenium_nairaland_scraper",
                    error="Timeout waiting for thread links."
                )]

            if not thread_links:
                print("No threads found.")  # Debug
                self.driver.quit()
                return [ToolResult(
                    title="No Results",
                    url=search_url,
                    snippet=f"No threads found for query: {query}",
                    source="nairaland",
                    tool_name="selenium_nairaland_scraper",
                    error="No matching threads."
                )]

            results = []
            for i, link in enumerate(thread_links):
                print(f"Scraping thread {i+1}: {link.get_attribute('href')}")  # Debug
                try:
                    link.click()
                    time.sleep(3)  # Wait for page load
                    result = self._scrape_thread()
                    results.append(result)
                    self.driver.back()
                    time.sleep(2)  # Rate limit
                except Exception as e:
                    print(f"Error scraping thread {i+1}: {type(e).__name__}: {e}")
                    results.append(ToolResult(
                        title="Thread Error",
                        url=link.get_attribute('href'),
                        snippet="Failed to scrape this thread.",
                        source="nairaland",
                        tool_name="selenium_nairaland_scraper",
                        error=f"{type(e).__name__}: {e}"
                    ))

            self.driver.quit()
            return results

        except WebDriverException as e:
            print(f"WebDriverException: {e}")
            self.driver.quit()
            return [ToolResult(
                title="Driver Error",
                url=self.BASE_URL,
                snippet=f"WebDriver issue: {e}",
                source="nairaland",
                tool_name="selenium_nairaland_scraper",
                error=f"WebDriverException: {e}"
            )]
        except Exception as e:
            print(f"General error in scrape_nairaland: {type(e).__name__}: {e}")
            self.driver.quit()
            return [ToolResult(
                title="Scraping Error",
                url=self.BASE_URL,
                snippet=f"General error: {type(e).__name__}: {e}",
                source="nairaland",
                tool_name="selenium_nairaland_scraper",
                error=f"{type(e).__name__}: {e}"
            )]

    def _scrape_thread(self) -> ToolResult:
        try:
            # Title
            title_elem = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='body']/h2"))
            )
            title = title_elem.text
            print(f"Scraped title: {title}")  # Debug

            # Snippet/Content
            content_elem = self.driver.find_element(By.XPATH, "//div[@class='post-body']")
            snippet = content_elem.text[:200] + "..."

            # Users and views (with fallbacks)
            try:
                p_elem = self.driver.find_element(By.XPATH, "//p[@class='nocopy']")
                p_text = p_elem.text
                user_list = [user.strip() for user in p_text.split(',')]
                num_users = len(user_list)
                guests_match = re.search(r'(\d+) guest', p_text)
                guests = int(guests_match.group(1)) if guests_match else 0
            except NoSuchElementException:
                num_users = 0
                guests = 0

            try:
                views_elem = self.driver.find_element(By.XPATH, "//p[@class='bold']")
                views_match = re.search(r'(\d+) Views', views_elem.text)
                views = int(views_match.group(1)) if views_match else 0
            except NoSuchElementException:
                views = 0

            return ToolResult(
                title=title,
                url=self.driver.current_url,
                snippet=snippet,
                source="nairaland",
                data_point={"views": views, "active_users": num_users, "guests": guests},
                confidence=0.8,
                metadata={"query": None},
                tool_name="selenium_nairaland_scraper"
            )

        except TimeoutException as e:
            print(f"Timeout scraping thread: {e}")
            return ToolResult(
                title="Thread Timeout",
                url=self.driver.current_url,
                snippet="Timed out loading thread.",
                source="nairaland",
                tool_name="selenium_nairaland_scraper",
                error=f"TimeoutException: {e}"
            )
        except NoSuchElementException as e:
            print(f"Element not found: {e}")
            return ToolResult(
                title="Element Not Found",
                url=self.driver.current_url,
                snippet="Required elements not found on thread page.",
                source="nairaland",
                tool_name="selenium_nairaland_scraper",
                error=f"NoSuchElementException: {e}"
            )

# Convenience function
def scrape_nairaland_selenium(query: str, driver_path: Optional[str] = None, max_results: int = 5, proxy: Optional[str] = None) -> List[ToolResult]:
    """
    :param driver_path: Optional path to chromedriver.exe. If None, uses Selenium Manager.
    """
    scraper = SeleniumNairalandScraper(driver_path, proxy)
    return scraper.scrape_nairaland(query, max_results)