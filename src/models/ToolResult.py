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
