import requests
from typing import Dict, Any
from langchain.tools import tool

from core.config import Config

# API credentials and settings (stored as variables for modularity)
RAPIDAPI_HOST = "local-business-search.p.rapidapi.com"
RAPIDAPI_KEY = Config.RAPID_API_KEY

BASE_URL = f"https://{RAPIDAPI_HOST}/business-details"

# Function to fetch business details using Local Business Search API
@ tool
def get_business_details(
    business_id: str,
    extract_emails_and_contacts: bool = True,
    extract_share_link: bool = False,
    region: str = "ng",
    language: str = "en",
    coordinates: str = None,
    fields: str = None
) -> Dict[str, Any]:
    """
    Fetches details for a specific business using the Local Business Search API.

    Parameters:
    - business_id (str): Unique business identifier (google_id, business_id, or place_id).
    - extract_emails_and_contacts (bool): Whether to extract emails, contacts, and social profiles for the business. Default is True.
    - extract_share_link (bool): Whether to extract the place's share link for the business. Default is False.
    - region (str): The region to query Google Maps from. Default is 'us'.
    - language (str): Language code for the results. Default is 'en'.
    - coordinates (str): Geographic coordinates for biasing the results. Defaults to None (use default region).
    - fields (str): Comma-separated list of business fields to include in the response (e.g., 'business_id,type,phone_number').

    Returns:
    - A dictionary containing business details.
    """
    
    # API request parameters
    params = {
        "business_id": business_id,
        "extract_emails_and_contacts": "true" if extract_emails_and_contacts else "false",
        "extract_share_link": "true" if extract_share_link else "false",
        "region": region,
        "language": language,
        "coordinates": coordinates,
        "fields": fields,
    }

    # Remove any optional parameters that are None
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