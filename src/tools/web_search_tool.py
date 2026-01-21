import json
import logging
import os
from typing import List, Optional, Type

from core.config import Config
from langchain_google_community import GoogleSearchAPIWrapper
from langchain_community.tools import DuckDuckGoSearchResults

from langchain_core.tools import tool
from src.models.ToolResult import ToolResult

logger = logging.getLogger(__name__)

# ============================================================================ 
# CONFIGURATION 
# ============================================================================

DEFAULT_MAX_RESULTS = Config.WS_MAX_RESULTS
TIMEOUT = Config.WS_TIMEOUT
RATE_LIMIT_DELAY = Config.WS_RATE_LIMIT_DELAY  # seconds between requests

# ============================================================================ 
# SEARCH WEB TOOL 
# ============================================================================

class WebSearchTool:
    """
    Domain-agnostic web search tool with Google + DuckDuckGo fallback.
    
    - Uses Google Search API if GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID are set
    - Falls back to DuckDuckGo if Google credentials are not available
    - Returns results as instances of ToolResult (instead of SourceDoc)
    """

    def __init__(self):
        """Initialize the web search tool."""
        self.google_available = self._check_google_credentials()
        
        # Initialize DuckDuckGo with news source for date and source fields
        self.duckduckgo_tool = DuckDuckGoSearchResults(
            output_format="list",
            max_results=DEFAULT_MAX_RESULTS,
            backend="text",
            source="news"  # Use news source for date and source fields
        )
        
        if self.google_available:
            logger.info("✅ Google Search API available")
            self.google_tool = GoogleSearchAPIWrapper()
        else:
            logger.info("⚠️  Google Search API not available, using DuckDuckGo")

    def _check_google_credentials(self) -> bool:
        """Check if Google Search API credentials are available."""
        api_key = os.getenv("GOOGLE_API_KEY")
        search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        
        if api_key and search_engine_id:
            return True
        return False

    def _enhance_query(self, query: str, geo_focus: Optional[str] = None, time_horizon: Optional[str] = None) -> str:
        """
        Enhance the search query with geo_focus and time_horizon.
        
        Args:
            query: Base search query
            geo_focus: Geographic focus (e.g., "Nigeria", "EU")
            time_horizon: Time horizon (e.g., "last_30_days", "last_5_years")
        
        Returns:
            Enhanced query string
        """
        enhanced = query
        
        if geo_focus and geo_focus.lower() != "global":
            enhanced += f" {geo_focus}"
        
        if time_horizon:
            if "last_30_days" in time_horizon:
                enhanced += " last 30 days"
            elif "last_5_years" in time_horizon:
                enhanced += " last 5 years"
            elif "last_year" in time_horizon:
                enhanced += " last year"
        
        logger.debug(f"Enhanced query: '{enhanced}'")
        return enhanced

    def _parse_google_results(self, results: str) -> List[dict]:
        """
        Parse Google Search API results into a simple dict format.
        
        Args:
            results: Raw results from Google API
        
        Returns:
            List of parsed results as dicts
        """
        parsed = []
        
        lines = results.split("\n")
        current_result = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line[0].isdigit() and "." in line[:3]:
                if current_result:
                    parsed.append(current_result)
                
                parts = line.split(" - ", 1)
                if len(parts) == 2:
                    title = parts[0].replace(f"{parts[0].split('.')[0]}.", "").strip()
                    link = parts[1].strip()
                    current_result = {
                        "title": title,
                        "link": link,
                        "snippet": ""
                    }
            elif current_result:
                current_result["snippet"] += line + " "
        
        if current_result:
            parsed.append(current_result)
        
        return parsed

    def _convert_to_tool_result(self, raw_result: dict, source_name: str, geo_focus: Optional[str] = None, time_horizon: Optional[str] = None) -> ToolResult:
        """
        Convert a raw search result to ToolResult format for web search.
        
        Args:
            raw_result: Raw search result dict (from Google or DuckDuckGo)
            source_name: Name of the search source ("Google" or "DuckDuckGo")
        
        Returns:
            ToolResult instance
        """
        url = raw_result.get("link") or raw_result.get("url", "")
        
        return ToolResult(
            title=raw_result.get("title", ""),
            url=url,
            snippet=raw_result.get("snippet", "").strip(),
            source=source_name,
            date=raw_result.get("date"),
            metadata={
                "search_source": source_name,
                "time_horizon": time_horizon or "all_time",
            }
        )

    def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS, geo_focus: Optional[str] = None, time_horizon: Optional[str] = None) -> List[ToolResult]:
        """
        Search the web for information and return results as ToolResult instances.
        
        Uses Google Search API if available, falls back to DuckDuckGo.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            geo_focus: Geographic focus (e.g., "Nigeria", "global")
            time_horizon: Time horizon (e.g., "last_30_days", "all_time")
        
        Returns:
            List of ToolResult instances
        
        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        logger.info(f"🔍 Searching web for: '{query}'")
        
        # Enhance query with geo and time parameters
        enhanced_query = self._enhance_query(query, geo_focus, time_horizon)
        
        try:
            # Try Google first
            if self.google_available:
                logger.debug("Using Google Search API")
                
                results_str = self.google_tool.run(enhanced_query, max_results=max_results)
                raw_results = self._parse_google_results(results_str)
                
                # Convert to ToolResult
                return [self._convert_to_tool_result(result, "Google", geo_focus, time_horizon) for result in raw_results[:max_results]]
            
            # Fall back to DuckDuckGo
            logger.debug("Using DuckDuckGo News Search")
            self.duckduckgo_tool.max_results = max_results
            results_output = self.duckduckgo_tool._run(enhanced_query)
            
            # Extract results
            if isinstance(results_output, tuple):
                raw_results = results_output[1]  # Get raw_results from tuple
            else:
                raw_results = results_output
            
            # Ensure raw_results is a list
            if isinstance(raw_results, str):
                try:
                    raw_results = json.loads(raw_results)
                except:
                    raw_results = []
            
            # Convert to ToolResult
            return [self._convert_to_tool_result(result, "DuckDuckGo", geo_focus, time_horizon) for result in raw_results[:max_results]]
        
        except Exception as e:
            logger.error(f"❌ Web search failed: {e}")
            raise

# ============================================================================ 
# CONVENIENCE FUNCTION 
# ============================================================================

@tool
def search_web(query: str, max_results: int = DEFAULT_MAX_RESULTS, geo_focus: Optional[str] = None, time_horizon: Optional[str] = None) -> List[ToolResult]:
    """
    Convenience function to search the web using the singleton WebSearchTool instance.
    
    Args:
        query: Search query
        max_results: Maximum number of results
        geo_focus: Geographic focus (e.g., "Nigeria", "global")
        time_horizon: Time horizon (e.g., "last_30_days", "all_time")
    
    Returns:
        List of ToolResult instances
    """
    tool = WebSearchTool()
    return tool.search(query, max_results, geo_focus, time_horizon)