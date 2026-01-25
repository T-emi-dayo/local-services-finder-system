import requests
from typing import Optional, Dict, Any, List
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
    data_point: dict = {}              # Always a dict: {"price": 150.25, "volume": 1M, ...}  # Changed to non-Optional with default {}
    confidence: Optional[float] = None # Data confidence (0-1)
    
    # Metadata and tracking
    metadata: dict = {}                # Tool-specific data
    tool_name: Optional[str] = None    # Which tool returned this
    
    # Error Handling
    error: Optional[str] = None        # Error message if tool failed

BASE_URL = "https://api.nairaland.ng"

class NairalandApiError(Exception):
    """Custom exception for API errors."""
    pass

def _handle_response(resp: requests.Response) -> Dict[str, Any]:
    """
    Validate and parse JSON response.
    Raises NairalandApiError if non-200 or invalid JSON.
    """
    if resp.status_code != 200:
        raise NairalandApiError(f"HTTP {resp.status_code} — {resp.text}")
    try:
        data = resp.json()
    except ValueError:
        raise NairalandApiError("Could not parse JSON response")
    return data

def ping_api() -> List[ToolResult]:
    """Ping the API to check if alive."""
    try:
        data = _handle_response(requests.get(BASE_URL))
        return [ToolResult(
            title="API Ping",
            url=BASE_URL,
            snippet=data.get('message', 'API is alive'),
            source="nairaland_api",
            data_point={"timestamp": data.get('timestamp'), "version": data.get('version'), "status": data.get('status')},
            confidence=1.0,
            tool_name="nairaland_api_tool"
        )]
    except NairalandApiError as e:
        return [ToolResult(
            title="Ping Error",
            url=BASE_URL,
            snippet="Failed to ping API.",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error=str(e)
        )]

def get_categories() -> List[ToolResult]:
    """Fetch categories (array of strings)."""
    try:
        data = _handle_response(requests.get(f"{BASE_URL}/categories"))
        results = []
        for cat in data:  # data is an array of strings
            results.append(ToolResult(
                title=cat,
                url=f"{BASE_URL}/posts?categories={cat}",
                snippet=f"Category: {cat}",
                source="nairaland_api",
                data_point={},
                confidence=0.9,
                metadata={"category": cat},
                tool_name="nairaland_api_tool"
            ))
        return results
    except NairalandApiError as e:
        return [ToolResult(
            title="Categories Fetch Error",
            url=f"{BASE_URL}/categories",
            snippet="Failed to fetch categories.",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error=str(e)
        )]

def get_top_posts(page: int = 1, per_page: int = 10) -> List[ToolResult]:
    """Fetch top posts."""
    try:
        params = {"page": page, "per_page": per_page}
        data = _handle_response(requests.get(f"{BASE_URL}/posts/top", params=params))
        results = []
        for post in data.get('posts', []):
            results.append(ToolResult(
                title=post.get('title', 'Unknown'),
                url=f"{BASE_URL}/posts/{post.get('postId', '')}",
                snippet=post.get('contentBrief', ''),
                source="nairaland_api",
                content=post.get('content'),
                authors=[post.get('author', {}).get('author', '')],
                date=post.get('publicationDate'),
                data_point={"pageViews": post.get('pageViews'), "commentsCount": post.get('commentsCount'), "likeCount": post.get('likeCount')},
                confidence=0.9,
                metadata={"postId": post.get('postId'), "hasMore": data.get('hasMore')},
                tool_name="nairaland_api_tool"
            ))
        return results
    except NairalandApiError as e:
        return [ToolResult(
            title="Top Posts Fetch Error",
            url=f"{BASE_URL}/posts/top",
            snippet="Failed to fetch top posts.",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error=str(e)
        )]

def search_posts(query: str, page: int = 1, per_page: int = 10, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[ToolResult]:
    """Search posts."""
    try:
        params = {"query": query, "page": page, "per_page": per_page}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        data = _handle_response(requests.get(f"{BASE_URL}/posts/search", params=params))
        results = []
        for post in data.get('posts', []):
            results.append(ToolResult(
                title=post.get('title', 'Unknown'),
                url=f"{BASE_URL}/posts/{post.get('postId', '')}",
                snippet=post.get('contentBrief', ''),
                source="nairaland_api",
                content=post.get('content'),
                authors=[post.get('author', {}).get('author', '')],
                date=post.get('publicationDate'),
                data_point={"pageViews": post.get('pageViews'), "commentsCount": post.get('commentsCount'), "likeCount": post.get('likeCount')},
                confidence=0.9,
                metadata={"postId": post.get('postId'), "hasMore": data.get('hasMore')},
                tool_name="nairaland_api_tool"
            ))
        return results
    except NairalandApiError as e:
        return [ToolResult(
            title="Search Error",
            url=f"{BASE_URL}/posts/search",
            snippet="Failed to search posts.",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error=str(e)
        )]

def get_posts_by_categories(categories: List[str], page: int = 1, per_page: int = 10, sort_order: str = "DESC") -> List[ToolResult]:
    """Fetch posts by categories."""
    try:
        params = {"categories": categories, "page": page, "per_page": per_page, "sort_order": sort_order}
        data = _handle_response(requests.get(f"{BASE_URL}/posts", params=params))
        results = []
        for post in data.get('posts', []):
            results.append(ToolResult(
                title=post.get('title', 'Unknown'),
                url=f"{BASE_URL}/posts/{post.get('postId', '')}",
                snippet=post.get('contentBrief', ''),
                source="nairaland_api",
                content=post.get('content'),
                authors=[post.get('author', {}).get('author', '')],
                date=post.get('publicationDate'),
                data_point={"pageViews": post.get('pageViews'), "commentsCount": post.get('commentsCount'), "likeCount": post.get('likeCount')},
                confidence=0.9,
                metadata={"postId": post.get('postId'), "hasMore": data.get('hasMore')},
                tool_name="nairaland_api_tool"
            ))
        return results
    except NairalandApiError as e:
        return [ToolResult(
            title="Posts by Categories Error",
            url=f"{BASE_URL}/posts",
            snippet="Failed to fetch posts by categories.",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error=str(e)
        )]

def get_post_details(post_id: int) -> List[ToolResult]:
    """Fetch a single post by ID."""
    try:
        data = _handle_response(requests.get(f"{BASE_URL}/posts/{post_id}"))
        return [ToolResult(
            title=data.get('title', 'Unknown'),
            url=f"{BASE_URL}/posts/{post_id}",
            snippet=data.get('contentBrief', ''),
            source="nairaland_api",
            content=data.get('content'),
            authors=[data.get('author', {}).get('author', '')],
            date=data.get('publicationDate'),
            data_point={"pageViews": data.get('pageViews'), "commentsCount": data.get('commentsCount'), "likeCount": data.get('likeCount'), "shareCount": data.get('shareCount')},
            confidence=0.9,
            metadata={"postId": data.get('postId'), "category": data.get('category')},
            tool_name="nairaland_api_tool"
        )]
    except NairalandApiError as e:
        return [ToolResult(
            title="Post Details Error",
            url=f"{BASE_URL}/posts/{post_id}",
            snippet="Failed to fetch post details.",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error=str(e)
        )]

def get_post_comments(post_id: int, comment_id: Optional[str] = None, page: int = 1, per_page: int = 10, sort_order: str = "DESC") -> List[ToolResult]:
    """Fetch comments for a post."""
    try:
        params = {"page": page, "per_page": per_page, "sort_order": sort_order}
        if comment_id:
            params["comment_id"] = comment_id
        data = _handle_response(requests.get(f"{BASE_URL}/posts/{post_id}/comments", params=params))
        results = []
        for comment in data.get('comments', []):
            results.append(ToolResult(
                title=f"Comment on Post {post_id}",
                url=f"{BASE_URL}/posts/{post_id}/comments",
                snippet=comment.get('content', '')[:200],
                source="nairaland_api",
                content=comment.get('content'),
                authors=[comment.get('author', '')],
                date=comment.get('publicationDate'),
                data_point={"likeCount": comment.get('likeCount')},
                confidence=0.9,
                metadata={"commentId": comment.get('commentId'), "hasMore": data.get('hasMore')},
                tool_name="nairaland_api_tool"
            ))
        return results
    except NairalandApiError as e:
        return [ToolResult(
            title="Post Comments Error",
            url=f"{BASE_URL}/posts/{post_id}/comments",
            snippet="Failed to fetch post comments.",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error=str(e)
        )]

def get_posts_by_author(author: str, page: int = 1, per_page: int = 10, sort_order: str = "DESC") -> List[ToolResult]:
    """Fetch posts by author."""
    try:
        params = {"page": page, "per_page": per_page, "sort_order": sort_order}
        data = _handle_response(requests.get(f"{BASE_URL}/posts/author/{author}", params=params))
        results = []
        for post in data.get('posts', []):
            results.append(ToolResult(
                title=post.get('title', 'Unknown'),
                url=f"{BASE_URL}/posts/{post.get('postId', '')}",
                snippet=post.get('contentBrief', ''),
                source="nairaland_api",
                content=post.get('content'),
                authors=[author],
                date=post.get('publicationDate'),
                data_point={"pageViews": post.get('pageViews'), "commentsCount": post.get('commentsCount'), "likeCount": post.get('likeCount')},
                confidence=0.9,
                metadata={"postId": post.get('postId'), "hasMore": data.get('hasMore')},
                tool_name="nairaland_api_tool"
            ))
        return results
    except NairalandApiError as e:
        return [ToolResult(
            title="Posts by Author Error",
            url=f"{BASE_URL}/posts/author/{author}",
            snippet="Failed to fetch posts by author.",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error=str(e)
        )]

def get_author_comments(author: str, page: int = 1, per_page: int = 10, sort_order: str = "DESC") -> List[ToolResult]:
    """Fetch comments by author."""
    try:
        params = {"page": page, "per_page": per_page, "sort_order": sort_order}
        data = _handle_response(requests.get(f"{BASE_URL}/posts/author/{author}/comments", params=params))  # Assuming endpoint based on doc
        results = []
        for comment in data.get('comments', []):
            results.append(ToolResult(
                title=f"Comment by {author}",
                url=f"{BASE_URL}/posts/author/{author}/comments",
                snippet=comment.get('content', '')[:200],
                source="nairaland_api",
                content=comment.get('content'),
                authors=[author],
                date=comment.get('publicationDate'),
                data_point={"likeCount": comment.get('likeCount')},
                confidence=0.9,
                metadata={"commentId": comment.get('commentId'), "hasMore": data.get('hasMore')},
                tool_name="nairaland_api_tool"
            ))
        return results
    except NairalandApiError as e:
        return [ToolResult(
            title="Author Comments Error",
            url=f"{BASE_URL}/posts/author/{author}/comments",
            snippet="Failed to fetch author comments.",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error=str(e)
        )]

# Convenience function for agents
def query_nairaland_api(query_type: str, **kwargs) -> List[ToolResult]:
    """
    Agent-friendly convenience function to query the Nairaland API.
    :param query_type: One of 'ping', 'categories', 'top_posts', 'search_posts', 'posts_by_categories', 'post_details', 'post_comments', 'posts_by_author', 'author_comments'.
    :param kwargs: Endpoint-specific params (e.g., query='politics', post_id=123, author='username').
    :return: List[ToolResult].
    """
    if query_type == 'ping':
        return ping_api()
    elif query_type == 'categories':
        return get_categories()
    elif query_type == 'top_posts':
        return get_top_posts(kwargs.get('page', 1), kwargs.get('per_page', 10))
    elif query_type == 'search_posts':
        return search_posts(kwargs['query'], kwargs.get('page', 1), kwargs.get('per_page', 10), kwargs.get('start_date'), kwargs.get('end_date'))
    elif query_type == 'posts_by_categories':
        return get_posts_by_categories(kwargs['categories'], kwargs.get('page', 1), kwargs.get('per_page', 10), kwargs.get('sort_order', 'DESC'))
    elif query_type == 'post_details':
        return get_post_details(kwargs['post_id'])
    elif query_type == 'post_comments':
        return get_post_comments(kwargs['post_id'], kwargs.get('comment_id'), kwargs.get('page', 1), kwargs.get('per_page', 10), kwargs.get('sort_order', 'DESC'))
    elif query_type == 'posts_by_author':
        return get_posts_by_author(kwargs['author'], kwargs.get('page', 1), kwargs.get('per_page', 10), kwargs.get('sort_order', 'DESC'))
    elif query_type == 'author_comments':
        return get_author_comments(kwargs['author'], kwargs.get('page', 1), kwargs.get('per_page', 10), kwargs.get('sort_order', 'DESC'))
    else:
        return [ToolResult(
            title="Invalid Query Type",
            url=BASE_URL,
            snippet=f"Unknown query_type: {query_type}",
            source="nairaland_api",
            tool_name="nairaland_api_tool",
            error="Supported: ping, categories, top_posts, search_posts, posts_by_categories, post_details, post_comments, posts_by_author, author_comments"
        )]