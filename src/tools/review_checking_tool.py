import requests
from typing import Dict, Any
from langchain.tools import tool

from core.config import Config

# API credentials and settings (stored as variables for modularity)
RAPIDAPI_HOST = "local-business-search.p.rapidapi.com"
RAPIDAPI_KEY = Config.RAPID_API_KEY

BASE_URL = "https://local-business-search.p.rapidapi.com/business-reviews-v2"

# Function to fetch business reviews using Local Business Search API
@tool
def get_business_reviews(
    business_id: str,
    limit: int = 20,
    cursor: str = None,
    translate_reviews: bool = False,
    query: str = None,
    sort_by: str = "most_relevant",
    fields: str = None,
    region: str = "us",
    language: str = "en"
) -> Dict[str, Any]:
    """
    Fetches reviews for a specific business using the Local Business Search API.

    Parameters:
    - business_id (str): Unique business identifier (google_id, business_id, or place_id).
    - limit (int): The maximum number of reviews to return (default is 20).
    - cursor (str): The cursor value for pagination (optional).
    - translate_reviews (bool): Whether to translate reviews to the specified language (default is False).
    - query (str): Filter reviews by matching text query (optional).
    - sort_by (str): Sort reviews by "most_relevant", "newest", "highest_ranking", or "lowest_ranking".
    - fields (str): Comma-separated list of fields to include in the response (optional).
    - region (str): The region to query reviews from (default is 'us').
    - language (str): The language for the reviews (default is 'en').

    Returns:
    - A dictionary containing business reviews.
    """
    
    # API request parameters
    params = {
        "business_id": business_id,
        "limit": limit,
        "cursor": cursor,
        "translate_reviews": "true" if translate_reviews else "false",
        "query": query,
        "sort_by": sort_by,
        "fields": fields,
        "region": region,
        "language": language,
    }

    # Remove any optional parameters that are None
    params = {key: value for key, value in params.items() if value is not None}

    # Headers for authentication
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    try:
        # Send the API request
        response = requests.get(BASE_URL, headers=headers, params=params)
        
        # Check for successful response
        response.raise_for_status()

        # Parse the response JSON
        review_data = response.json()

        # Return review data
        return review_data
    
    except requests.exceptions.RequestException as e:
        # Handle any errors with the request
        return {"error": f"An error occurred: {str(e)}"}