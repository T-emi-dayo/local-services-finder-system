High-Priority Tools
1. Google Maps API / Places API

Structured business data (name, phone, hours, ratings)
Geographic clustering and proximity search
Verified business information
User reviews and photos

2. Social Media Scrapers

WhatsApp Business Directory - Critical for Nigerian market where WhatsApp is primary contact method
Facebook Pages/Groups - Many Nigerian businesses operate primarily on Facebook
Instagram Business Profiles - Contact info in bios, Stories highlights
Twitter/X Search - Real-time recommendations, complaints, service announcements

3. Nigerian-Specific Directories

Jiji.ng - Classified ads with service providers
Connect Nigeria Directory
Vconnect.com - Business directory
YellowPages Nigeria

4. Forum/Community Tools

Nairaland scraper (as you mentioned)
Reddit Nigeria - r/Nigeria, r/Lagos
Telegram groups - Many area-specific service groups exist

5. Review Aggregator

Google Reviews fetcher
Facebook Recommendations parser
Sentiment analysis across multiple sources

Medium-Priority Tools
6. Price Intelligence Tool

Scrape mentioned prices from sources
Build price ranges per service category
Compare against user's budget_band

7. Phone Number Validator

Verify Nigerian phone format (+234...)
Check if number is active/WhatsApp-enabled
Deduplicate candidates with same phone

8. Business Verification Tool

Check CAC (Corporate Affairs Commission) registration
Verify business exists beyond just social media
Flag potential scams

9. Recency Scorer

Parse dates from reviews/posts
Score candidates based on recent activity
Flag inactive businesses

Nigerian Market-Specific Considerations
10. Payment Method Detector

Extract accepted payment methods (cash, transfer, POS)
Flag providers accepting bank transfer (trust signal)

11. Location Landmark Matcher

Nigerian addresses often use landmarks
Tool to match "near Shoprite" to coordinates
Area nickname resolver (e.g., "Gwarinpa" variations)

12. Language/Pidgin Parser

Handle Nigerian English, pidgin in reviews
Sentiment analysis tuned for local expressions

Tool Architecture Suggestion
pythonfrom enum import Enum

class ToolType(str, Enum):
    # Search & Discovery
    WEB_SEARCH = "web_search"
    MAPS_SEARCH = "maps_search"
    FORUM_SEARCH = "forum_search"  # Nairaland
    SOCIAL_SEARCH = "social_search"  # FB, IG, Twitter
    DIRECTORY_SEARCH = "directory_search"  # Jiji, Vconnect
    
    # Enrichment
    BUSINESS_VERIFY = "business_verify"
    PHONE_VALIDATE = "phone_validate"
    REVIEW_AGGREGATE = "review_aggregate"
    PRICE_EXTRACT = "price_extract"
    
    # Scoring
    RECENCY_SCORE = "recency_score"
    SENTIMENT_ANALYZE = "sentiment_analyze"
    LOCATION_MATCH = "location_match"
Recommended Minimal Viable Toolset
Start with these 5 tools:

Web Search (general)
Google Maps API (structured business data)
Nairaland Scraper (community trust signals)
WhatsApp Business Checker (critical for Nigerian market)
Phone Validator (deduplication + WhatsApp verification)

Then add based on performance gaps in your testing.