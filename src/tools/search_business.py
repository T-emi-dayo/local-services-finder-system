import requests
from typing import Dict, Any
from langchain.tools import tool

from core.config import Config

# API credentials and settings
RAPIDAPI_HOST = "local-business-search.p.rapidapi.com"
RAPIDAPI_KEY = Config.RAPID_API_KEY

BASE_URL = f"https://{RAPIDAPI_HOST}/search"

# Function to fetch business details using Local Business Search API
@tool
def search_local_businesses(
    query: str,
    limit: int = 20,
    lat: float = 37.359428,
    lng: float = -121.925337,
    zoom: int = 13,
    language: str = "en",
    region: str = "ng",
    subtypes: str = None,
    verified: bool = False,
    business_status: str = None,
    extract_emails_and_contacts: bool = False,
    fields: str = None
) -> Dict[str, Any]:
    """
    Searches for local businesses using the Local Business Search API.

    Parameters:
    - query (str): The type of service or business to search for (e.g., "Plumbers near New-York, USA").
    - limit (int): The maximum number of businesses to return. Default is 20.
    - lat (float): Latitude for biasing search results. Default is 37.359428.
    - lng (float): Longitude for biasing search results. Default is -121.925337.
    - zoom (int): Zoom level for the search. Default is 13.
    - language (str): The language of the results. Default is 'en'.
    - region (str): Region/country code for the search. Default is 'us'.
    - subtypes (str): Comma-separated list of business categories (e.g., 'Plumber,Carpenter,Electrician').
    - verified (bool): Whether to only return verified businesses. Default is False.
    - business_status (str): Business status filter (e.g., 'OPEN', 'CLOSED').
    - extract_emails_and_contacts (bool): Whether to extract emails and contacts for businesses.
    - fields (str): Comma-separated list of fields to include in the response.

    Returns:
    - A dictionary containing business information.
    """
    
    # API request parameters
    params = {
        "query": query,
        "limit": limit,
        "lat": lat,
        "lng": lng,
        "zoom": zoom,
        "language": language,
        "region": region,
        "subtypes": subtypes,
        "verified": "true" if verified else "false",
        "business_status": business_status,
        "extract_emails_and_contacts": "true" if extract_emails_and_contacts else "false",
        "fields": fields,
    }

    # Remove any optional parameters that are None (to avoid sending empty values)
    params = {key: value for key, value in params.items() if value is not None}

    # Headers for authentication
    headers = {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    try:
        # Send the API request
        response = requests.get(BASE_URL, headers=headers, params=params)
        
        # Check for successful response
        response.raise_for_status()

        # Parse the response JSON
        business_data = response.json()

        # Return business data
        return business_data
    
    except requests.exceptions.RequestException as e:
        # Handle any errors with the request
        return {"error": f"An error occurred: {str(e)}"}