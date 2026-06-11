# Local Services Finder — Architecture & Design (v2)

> **Last updated:** 2026-04-13
> **Status:** Core architecture implemented. Tool normalisation in progress (pending real API output inspection via test_tools.py).

---

## 1. Product Definition

### 1.1 What the system is
An AI-first local services discovery system for the Nigerian market. It accepts a structured user request and uses a deterministic multi-node pipeline to find, validate, and rank local service providers — returning the top 3 as contact-ready results.

### 1.2 What the system is not
- Not a generic chatbot.
- Not a web crawler or scraper.
- Not a CRM or marketplace.

### 1.3 Core outputs
- Up to **3** ranked provider recommendations (fewer if scarcity).
- Each result includes: name, phones, location, service tags, price signal, and a ranked evidence note explaining why the provider was selected.
- If no valid providers are found, a contextual no-result message with a reason.

---

## 2. Design Principles

1. **Semantics over form inputs** — the system infers the real service need from `additional_details`, not just `service_type`. If a user says they need an "electrician to fix their car AC", the system corrects this to "auto mechanic".
2. **Deterministic where possible** — fallback logic, completeness thresholds, and ranking criteria are code, not LLM decisions.
3. **Non-blocking failures** — no node crashes the graph. Every failure is caught, logged, and a meaningful message is returned via the synthesis node.
4. **Progressive enrichment** — candidates start sparse and are enriched in place as more data is gathered. A single `RawCandidate` schema is used throughout.
5. **Always reach synthesis** — the synthesis node is the single terminal node for all paths, including errors and empty results.

---

## 3. Inputs

### 3.1 FormConfig
```python
class FormConfig(BaseModel):
    service_type: str          # e.g. "Plumber", "Generator Repair"
    location_city: str         # e.g. "Lagos", "Abuja"
    location_area: str         # e.g. "Lekki", "Gwarimpa"
    urgency: Literal["IMMEDIATELY", "TODAY", "THIS_WEEK", "NOT_URGENT"]
    budget: Literal["LOW", "MEDIUM", "HIGH", "NO_BUDGET"]
    additional_details: str    # Optional free-text problem description
```

**Key rule:** `additional_details` always wins over `service_type` when they conflict. The stated service type is treated as a hint, not a contract.

---

## 4. Architecture Overview

### 4.1 Graph structure

```
FormConfig
    │
    ▼
┌──────────────────────────────────────────┐
│  Node 1+2: Intent Resolution             │  LLM (single call)
│  Validates and corrects service type     │
│  Generates primary + fallback params     │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Node 3: Tool Orchestration              │  Programmatic
│                                          │
│  Tier 1 — Discovery:                     │
│    search_local_businesses               │
│    → quality gate                        │
│    → fallback (wider params) if needed   │
│                                          │
│  Tier 2 — Enrichment (per candidate):    │
│    get_business_details  (by business_id)│
│    get_business_reviews  (by business_id)│
└──────────────────┬───────────────────────┘
                   │
          0 results? ──────────────────────────────────┐
                   │                                   │
                   ▼                                   │
┌──────────────────────────────────────────┐           │
│  Node 4: Cleanup                         │  Mixed    │
│                                          │           │
│  1. Completeness filter (programmatic)   │           │
│  2. Logical validation (LLM)            │           │
│  3. Semantic deduplication (LLM)        │           │
└──────────────────┬───────────────────────┘           │
                   │                                   │
          0 remain? ───────────────────────────────────┤
                   │                                   │
                   ▼                                   ▼
┌──────────────────────────────────────────────────────────┐
│  Node 5: Ranking & Synthesis                             │  LLM
│                                                          │
│  If candidates present:                                  │
│    Rank by explicit criteria                             │
│    Ranking rationale → per-candidate evidence text       │
│    Return top 3                                          │
│                                                          │
│  If no candidates (any reason):                          │
│    Return contextual no-result message                   │
└──────────────────────────────────────────────────────────┘
```

### 4.2 Routing

| Condition | Route |
|---|---|
| `synthesis_reason == "not_found"` | Node 3 → Node 5 (skip cleanup) |
| `synthesis_reason == "failed_validation"` | Node 4 → Node 5 |
| All other paths | Node 3 → Node 4 → Node 5 |

`synthesis_reason` is a string field on `AgentState` set by any node. Node 5 always executes.

---

## 5. Node Specifications

### 5.1 Node 1+2 — Intent Resolution & Search Param Generation

**Why merged:** Intent resolution produces the corrected service + enriched search terms that param generation needs as its primary input. Merging removes a redundant LLM round-trip with no architectural trade-off at current scope.

**LLM output schema (`IntentAndSearchParams`):**
```python
class IntentAndSearchParams(BaseModel):
    resolved_service: str       # corrected service type
    search_terms: List[str]     # synonyms for improved search recall
    correction_applied: bool    # True if additional_details overrode service_type

    primary_query: str          # specific: "generator repair Lekki Lagos"
    primary_subtypes: str       # comma-separated Maps business categories
    primary_lat: float          # coordinates of the target area
    primary_lng: float

    fallback_query: str         # wider: "generator repair Lagos"
    fallback_subtypes: str      # broader categories for fallback
```

**Failure behaviour:** If the LLM call fails, a deterministic fallback is applied using raw form values. Node 1+2 is never a blocking node — the graph always continues.

---

### 5.2 Node 3 — Tool Orchestration

**Active tools:**
| Tool | Tier | Input | Purpose |
|---|---|---|---|
| `search_local_businesses` | 1 | query, lat, lng, subtypes | Candidate discovery |
| `get_business_details` | 2 | business_id | Contact + category enrichment |
| `get_business_reviews` | 2 | business_id | Review snippet enrichment |

**Deferred:** `map_search_tool` — integration planned as a future improvement.
**Removed:** `web_search_tool`, `web_scrapping_tool`, `current_time_tool` — not applicable to structured tool orchestration.

**Tier 1 flow:**
1. Run `search_local_businesses` with primary params
2. Check quality gate: `>= 5 candidates with completeness_score >= 2`
3. If gate fails: rerun with fallback params, merge results
4. Proceed with whatever exists after one fallback attempt (no further retries)
5. If 0 candidates: set `synthesis_reason = "not_found"`, exit early

**Tier 2 flow:**
- For each candidate that has a `business_id`, call `get_business_details` then `get_business_reviews`
- Update the `RawCandidate` in place with enriched data
- Candidates without a `business_id` skip Tier 2 and proceed to cleanup as-is

**Normalization:** Every tool response is immediately mapped to `RawCandidate` before any further processing. Enrichment updates the same instance.

---

### 5.3 Node 4 — Cleanup

Three sequential steps. Each reduces noise before the next runs, minimising LLM token cost.

| Step | Method | Drops candidates if |
|---|---|---|
| 1. Completeness filter | Programmatic | `completeness_score() < 2` |
| 2. Logical validation | LLM | Location/city mismatch, invalid phone, unrelated business name |
| 3. Semantic dedup | LLM | Same real-world business as another candidate |

If candidates reach 0 after any step: `synthesis_reason = "failed_validation"`, exit to Node 5.

**LLM behaviour:** Both LLM steps are non-blocking. If the call fails, the step is skipped (pass-through) and a warning is logged.

**Completeness score** (defined on `RawCandidate`):
- +1 for each of: `name`, `phones`, `location`, `service_tags`, `source`
- Max score: 5

---

### 5.4 Node 5 — Ranking & Synthesis

**Ranking criteria (applied in order):**
1. Profile completeness — more fields filled = higher rank
2. Budget alignment — LOW budget prefers LOW/MID price_signal
3. Service tag relevance — tag match to resolved service
4. Location proximity — area match preferred over city-only match

The LLM ranks against these explicit criteria. Its reasoning per candidate becomes the `evidence` field on the `RawCandidate`. The overall rationale becomes `summary`.

**No-result messages** (by `synthesis_reason`):
- `not_found` — nothing returned from tool search
- `failed_validation` — results found but all failed cleanup
- `system_error` — unhandled exception in any node

---

## 6. Data Schemas

### 6.1 RawCandidate (single schema throughout)
```python
class RawCandidate(BaseModel):
    name: str
    phones: List[str]
    whatsapp_number: Optional[str]
    location: Optional[str]
    service_tags: List[str]
    price_signal: Literal["LOW", "MID", "HIGH", "PREMIUM", "UNKNOWN"]
    source: Optional[str]
    business_id: Optional[str]   # required for Tier 2 enrichment
    website: Optional[str]
    email: Optional[str]
    rating: Optional[float]
    reviews_summary: Optional[str]
    evidence: Optional[str]      # set by Node 5 ranking rationale
```

### 6.2 AgentState
```python
class AgentState(BaseModel):
    config: FormConfig
    intent: Optional[IntentAndSearchParams]
    raw_candidates: List[RawCandidate]      # Node 3 output
    sources: List[str]
    clean_candidates: List[RawCandidate]    # Node 4 output
    final_candidates: List[RawCandidate]    # Node 5 output (evidence set)
    summary: str
    synthesis_reason: str                   # routing + no-result context
```

---

## 7. Logging Strategy

### 7.1 Terminal logging (INFO)
Visible at runtime. Covers:
- Node entry and exit with `=` separator banners
- Candidate counts at each stage
- Routing decisions
- Tool names being called per candidate
- Final result count

Format example:
```
INFO  ============================================================
INFO  NODE 3 | Tool Orchestration
INFO    [Tier 1] Primary search: 'plumber Lekki Lagos'
INFO    [Tier 1] Primary returned 4 candidates
INFO    [Tier 1] Quality gate failed — running fallback
INFO  ROUTE | orchestrate_tools -> cleanup
```

### 7.2 File logging (DEBUG)
Stored to file for post-run inspection. Covers:
- Full LLM prompt and structured response per call
- Full tool input parameters and raw API response per call
- Exception tracebacks

**Status:** Planned. Will be added to `ToolOrchestrationNode` and LLM calls in `IntentResolutionNode`, `CleanupNode`, and `RankingSynthesisNode` once tool normalisation is finalised.

---

## 8. API & Frontend

### 8.1 API (FastAPI — app.py)

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the frontend |
| `/api/search` | POST | Accepts `FormConfig`, returns `{"job_id": "..."}` |
| `/api/status/{job_id}` | GET | Polls job: `{status, result?, error?}` |
| `/docs` | GET | Auto-generated Swagger UI |

The graph runs via `asyncio.to_thread` — the event loop is never blocked. Job results are held in an in-memory dict (sufficient for MVP).

**Job status values:**
- `running` — graph executing
- `done` — result ready, includes `candidates`, `summary`, `sources`
- `error` — unhandled exception, includes `error` string

### 8.2 Frontend (frontend/index.html)
Single-file HTML/CSS/JS. Polls `/api/status/{job_id}` every 2.5s after submitting.

**Form fields collected:**
- Service type (text input)
- City (dropdown: Lagos, Abuja, Port Harcourt, Kano, Ibadan, Enugu, Kaduna)
- Area / Neighbourhood (text input)
- Urgency (pill buttons: Immediately / Today / This Week / Not Urgent)
- Budget (pill buttons: Low / Medium / High / No Budget Set)
- Additional details (textarea, optional)

**Results display:**
- Summary banner
- Ranked candidate cards (name, price badge, phone links, WhatsApp link, location, service tags, evidence text)

---

## 9. Deferred Items

The following are intentionally out of scope for the current phase and will be addressed after the core is confirmed working end-to-end:

| Item | Reason deferred |
|---|---|
| Intent resolution failure edge | Requires stable core first |
| Loop / recovery path (0 candidates after cleanup → retry with wider params) | Future improvement |
| Map search tool integration (`map_search_tool`) | Circling back later |
| File-based DEBUG logging | Pending finalisation of tool normalisation |
| Database-backed job storage | In-memory dict sufficient for MVP |

---

## 10. Implementation Status

| Component | Status |
|---|---|
| FormConfig schema | Done |
| RawCandidate schema | Done |
| IntentAndSearchParams schema | Done |
| AgentState | Done |
| Node 1+2: IntentResolutionNode | Done |
| Node 3: ToolOrchestrationNode | Partially done — tool field mapping needs update after real API inspection |
| Node 4: CleanupNode | Done |
| Node 5: RankingSynthesisNode | Done |
| graph.py (LangGraph wiring) | Done |
| FastAPI backend (app.py) | Done |
| Frontend (index.html) | Done |
| Tool output schema test (tests/test_tools.py) | In progress |
| Deep file logging | Pending |
