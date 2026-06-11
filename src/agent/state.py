from pydantic import BaseModel, Field
from typing import List, Optional

from src.models.FormConfig import FormConfig
from src.models.SearchParams import IntentAndSearchParams
from src.models.RawCandidate import RawCandidate
class AgentState(BaseModel):
    # Input
    config: FormConfig

    # Node 1+2 output
    intent: Optional[IntentAndSearchParams] = None

    # Node 3 output - raw, unenriched + enriched candidates
    raw_candidates: List[RawCandidate] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)

    # Node 4 output - validated and deduplicated
    clean_candidates: List[RawCandidate] = Field(default_factory=list)

    # Node 5 output - final ranked results
    final_candidates: List[RawCandidate] = Field(default_factory=list)
    summary: str = ""

    # Routing signal - set by any node to inform synthesis of the outcome
    # "success"          - normal flow, candidates found and ranked
    # "not_found"        - tool search returned 0 results
    # "failed_validation"- cleanup removed all candidates
    # "system_error"     - unhandled exception in a node
    synthesis_reason: str = "success"
