from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class RawCandidate(BaseModel):
    """
    Progressive enrichment schema. Starts sparse after Tier 1 discovery,
    gets filled in as Tier 2 enrichment tools run.
    """
    name: str
    phones: List[str] = Field(default_factory=list)
    whatsapp_number: Optional[str] = None
    location: Optional[str] = None
    service_tags: List[str] = Field(default_factory=list)
    price_signal: Literal["LOW", "MID", "HIGH", "PREMIUM", "UNKNOWN"] = "UNKNOWN"
    # On the price, the idea of a price field is vague. Either explore the idea of a numerical price range or remove it all together.
    
    source: Optional[str] = None
    business_id: Optional[str] = None  # required for Tier 2 enrichment
    website: Optional[str] = None
    email: Optional[str] = None
    rating: Optional[float] = None
    reviews_summary: Optional[str] = None
    evidence: Optional[str] = None

    def completeness_score(self) -> int:
        """Count of key profile fields that are populated."""
        score = 0
        if self.name:         score += 1
        if self.phones:       score += 1
        if self.location:     score += 1
        if self.service_tags: score += 1
        if self.source:       score += 1
        return score
