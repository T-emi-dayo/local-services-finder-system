"""
Current Time Tool
Provides accurate real-time date and time information.
Works offline (system clock) or online (optional API fallback).
"""

import requests
from datetime import datetime
from langchain_core.tools import tool

@tool
def get_current_time_local() -> str:
    """
    Returns the current system date and time in a readable format.
    Example: "Tuesday, October 21, 2025, 16:04:32"
    """
    return datetime.now().strftime("%A, %B %d, %Y, %H:%M:%S")

@tool
def get_current_time_api() -> str:
    """
    Fetch the current real-world date and time. Use this tool for all queries involving 'today', 'now', 'current date', "or 'current time' instead of model memory.
    """
    try:
        res = requests.get("http://worldtimeapi.org/api/ip", timeout=5)
        res.raise_for_status()
        data = res.json()
        current_time = data.get("datetime", "")
        timezone = data.get("timezone", "UTC")
        return f"{current_time} ({timezone})"
    except Exception:
        # Fallback to system time if API unavailable
        return get_current_time_local()