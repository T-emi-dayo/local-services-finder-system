from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from uuid import uuid4


class PriceSignal(str, Enum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"
    PREMIUM = "PREMIUM"
    UNKNOWN = "UNKNOWN"


class UrgencyFit(str, Enum):
    IMMEDIATELY = "IMMEDIATELY"
    URGENT = "URGENT"
    SOON = "SOON"
    FLEXIBLE = "FLEXIBLE"
    UNKNOWN = "UNKNOWN"


class Sentiment(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class RecencySignal(str, Enum):
    RECENT = "RECENT"
    MODERATE = "MODERATE"
    OLD = "OLD"
    UNKNOWN = "UNKNOWN"


class EvidenceSource(str, Enum):
    MAPS = "maps"
    WEB = "web"
    SOCIAL = "social"
    FORUM = "forum"


class ExtractedFrom(str, Enum):
    LISTING = "listing"
    REVIEW = "review"
    POST = "post"
    COMMENT = "comment"


class Evidence(BaseModel):
    source: EvidenceSource
    url: Optional[str] = None
    snippet: str
    extracted_from: ExtractedFrom


class ServiceCandidate(BaseModel):
    candidate_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this service candidate, automatically generated as a UUID"
    )
    name: str = Field(
        ...,
        description="The business name or service provider name as it appears in the source"
    )
    phones: List[str] = Field(
        default_factory=list,
        description="List of contact phone numbers for the service provider, including country code where available"
    )
    whatsapp_available: bool = Field(
        False,
        description="Whether WhatsApp contact is explicitly mentioned or available for this provider"
    )
    location_city: str = Field(
        ...,
        description="The city where this service provider operates or is based"
    )
    location_area: Optional[str] = Field(
        None,
        description="Specific neighborhood, area, or district within the city where the provider is located"
    )
    address_hint: Optional[str] = Field(
        None,
        description="Partial address, street name, or landmark information that helps locate the provider"
    )
    service_tags: List[str] = Field(
        default_factory=list,
        description="List of service categories, specializations, or keywords describing what this provider offers (e.g., 'plumbing', 'emergency repair', 'leak fixing')"
    )
    service_match_confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence score (0.0 to 1.0) indicating how well this candidate matches the user's service request based on service type, location, and requirements"
    )
    price_signal: PriceSignal = Field(
        PriceSignal.UNKNOWN,
        description="Inferred or stated price range of the service provider based on mentions, comparisons, or explicit pricing information"
    )
    urgency_fit: UrgencyFit = Field(
        UrgencyFit.UNKNOWN,
        description="Assessment of how well this provider can meet the urgency requirements (e.g., offers emergency service, same-day availability)"
    )
    sentiment: Sentiment = Field(
        Sentiment.UNKNOWN,
        description="Overall sentiment derived from reviews, ratings, and mentions about this service provider"
    )
    sentiment_confidence: float = Field(
        0.5,
        ge=0,
        le=1,
        description="Confidence score (0.0 to 1.0) in the sentiment assessment, based on volume and consistency of sentiment signals"
    )
    recency_signal: RecencySignal = Field(
        RecencySignal.UNKNOWN,
        description="How recent the information about this provider is, based on review dates, post dates, or listing updates"
    )
    evidence: Evidence = Field(
        ...,
        description="The primary piece of evidence supporting this candidate, including source, URL, and relevant text snippet"
    )