# Local Services AI System — Architecture & Design (v1)

> **Purpose:** This document specifies an end-to-end *AI-first* architecture for a Local Services discovery system that takes **structured form inputs** (service type, location, budget, urgency + optional constraints) and uses **agentic tool-use** to search public sources, **extract** provider candidates, **deduplicate**, **score/rank**, and return the **Top 5 best-fit providers** as contact-ready cards.

---

## 1. Product Definition

### 1.1 What the system is
A tool-using AI system that converts a user’s structured request (via form) into:
1) a **search plan** (query generation and strategy),
2) **multi-source retrieval** via tools,
3) **structured candidate extraction** from raw results,
4) **entity resolution** (merge duplicates across sources),
5) **deterministic scoring/ranking** aligned to constraints,
6) **top-5 provider cards** with evidence-based reasoning.

### 1.2 What the system is *not*
- Not a generic chatbot for small talk.
- Not a full CRM or marketplace.
- Not a “scrape everything” crawler.

### 1.3 Core outputs
- Exactly **5** (or fewer if scarcity) provider recommendations.
- Each recommendation includes: name, contact, location, fit reason(s), evidence/source links, and confidence.

---

## 2. Design Goals

### 2.1 Primary goals (AI skill demonstration)
- **Query intelligence:** rewrite, diversify, and constrain queries to maximize relevant providers.
- **Tool-use competence:** choose sources, call tools efficiently, stop early when confident.
- **Extraction robustness:** convert messy web/social/forum results into structured provider candidates.
- **Decision quality:** transparent scoring and stable ranking logic.

### 2.2 Secondary goals (supporting engineering)
- Observability (logs, traces, replay).
- Repeatability (re-run same intent → comparable outcomes).
- Safety (avoid scams/red flags; avoid private/login scraping).

---

## 3. Inputs and Canonical Intent

### 3.1 FormConfig (user-provided structured input)
**Required**
- `service_type`: string (e.g., “Plumber”, “Vulcanizer”, “Generator repair”)
- `location_city`: string (e.g., “Abuja”)
- `location_area`: string (e.g., “Gwarimpa”)
- `urgency`: enum { `IMMEDIATELY`, `TODAY`, `THIS_WEEK`, `NOT_URGENT` }
- `budget_band`: enum { `LOW`, `MID`, `HIGH`, `NOT_SURE` }

**Optional** (high-value constraints)
- `issue_description`: string (1–3 sentences)
- `availability_window`: string (e.g., “after 6pm”, “now”, “weekend”)
- `contact_preference`: enum { `CALL`, `WHATSAPP`, `SMS`, `ANY` }
- `whatsapp_only`: boolean
- `proximity_preference`: enum { `NEARBY`, `ANYWHERE_IN_CITY`, `NEAR_LANDMARK` }
- `landmark`: string
- `price_sensitivity`: enum { `CHEAP`, `BALANCED`, `PREMIUM`, `UNKNOWN` }
- `safety_preferences`: object { `requires_id`: bool, `female_provider_only`: bool, `notes`: string }
- `language`: enum { `EN`, `PIDGIN`, `MIXED` }

### 3.2 CanonicalIntent (normalized by AI)
Derived from FormConfig (plus optional clarification) and used everywhere downstream.
- Normalizes service synonyms (e.g., “vulcanizer” ↔ “tyre repair”).
- Normalizes location names (case, abbreviations).
- Extracts keywords from issue_description.

---

## 4. High-Level Architecture

### 4.1 Core pipeline (recommended)

1) **Query Generation Node (Planner)**
   - Input: FormConfig
   - Output: SearchPlan

2) **Search+Extraction Agent (Merged Node)**
   - Input: SearchPlan
   - Uses tools: Web Search, Maps Search, Social Search, Forum Search
   - Output: Candidate[] (strict JSON)

3) **Entity Resolution Node (Deterministic)**
   - Input: Candidate[]
   - Output: ProviderProfile[]

4) **Scoring & Ranking Node (Deterministic)**
   - Input: ProviderProfile[], CanonicalIntent
   - Output: Top5[] with scores + reason codes

5) **Response Formatting Node**
   - Input: Top5[]
   - Output: Provider cards for UI


### 4.2 Why this design
- The agent handles the “AI work”: planning, tool use, extraction, adaptive search loops.
- Deterministic ranker ensures stability and debuggability.
- Separation allows systematic iteration without prompt chaos.

---

## 5. Node Specifications

## 5.1 Node 1 — Query Generation (Planner)

### 5.1.1 Responsibilities
- Convert form inputs into a **SearchPlan** optimized for retrieval.
- Generate **diverse** queries (synonyms, constraints, qualifiers).
- Select platform emphasis (Maps-heavy vs Web-heavy vs Social-heavy).
- Define stop conditions and budgets.

### 5.1.2 SearchPlan schema
```json
{
  "canonical_intent": {
    "service_type": "plumber",
    "location_city": "Abuja",
    "location_area": "Gwarimpa",
    "urgency": "IMMEDIATELY",
    "budget_band": "MID",
    "constraints": {
      "whatsapp_only": true,
      "landmark": "...",
      "price_sensitivity": "CHEAP"
    },
    "keywords": ["leak", "burst pipe"]
  },
  "query_sets": {
    "maps": ["plumber in Gwarimpa Abuja", "emergency plumber Gwarimpa WhatsApp"],
    "web": ["Gwarimpa plumber phone number", "recommended plumber Gwarimpa Abuja"],
    "social": ["plumber Gwarimpa Abuja WhatsApp", "any good plumber in Gwarimpa"],
    "forum": ["site:nairaland.com plumber Gwarimpa", "nairaland recommended plumber Abuja"]
  },
  "platform_hints": {
    "maps_weight": 0.45,
    "web_weight": 0.35,
    "social_weight": 0.15,
    "forum_weight": 0.05
  },
  "loop_policy": {
    "max_rounds": 2,
    "max_tool_calls": 12,
    "target_unique_candidates": 20,
    "early_stop_if_high_confidence": true
  },
  "stop_conditions": {
    "min_high_score_candidates": 5,
    "high_score_threshold": 0.72,
    "time_budget_ms": 7000
  },
  "risk_flags": ["scam_sensitive"]
}
```

### 5.1.3 Query diversification strategy
The planner should produce:
- **Core query:** service + area + city
- **Synonym variants:** local terms, alternative spellings
- **Constraint variants:** “WhatsApp”, “home service”, “24 hours”, “cheap”, “near [landmark]”
- **Trust variants:** “recommended”, “reviews”, “trusted”

### 5.1.4 Output contract
- Always output valid JSON for SearchPlan.
- Never invent private data.

---

## 5.2 Node 2 — Search+Extraction Agent (Merged)

### 5.2.1 Responsibilities
- Execute tool calls based on SearchPlan.
- Read tool outputs (snippets, listings, posts).
- Extract structured **Candidate** objects.
- Loop (bounded) if results are insufficient.

### 5.2.2 Tool interface (conceptual)
Each tool returns a list of results:
- `title`, `snippet`, `url`, `source`, `published_at` (if available), `raw_text`.

Tools (typical):
- `web_search(query)`
- `maps_search(query)`
- `social_search(query)`
- `forum_search(query)`

### 5.2.3 Candidate schema
```json
{
  "candidate_id": "uuid",
  "name": "Kenny Plumbing Services",
  "phones": ["+2348012345678"],
  "whatsapp_available": true,
  "location_city": "Abuja",
  "location_area": "Gwarimpa",
  "address_hint": "3rd Avenue, Gwarimpa",
  "service_tags": ["plumbing", "leak repair"],
  "service_match_confidence": 0.86,
  "price_signal": "MID",
  "urgency_fit": "IMMEDIATELY",
  "sentiment": "POSITIVE",
  "sentiment_confidence": 0.72,
  "recency_signal": "RECENT",
  "evidence": {
    "source": "maps",
    "url": "...",
    "snippet": "Emergency plumbing, leak repair... call/WhatsApp...",
    "extracted_from": "listing"
  }
}
```

### 5.2.4 Extraction rules (practical)
**Hard rules (deterministic):**
- Phone normalization:
  - Convert `080...` to `+23480...`
  - Accept `+234...` as-is
  - Remove spaces/dashes
- Deduplicate candidates within a single tool call by phone.

**LLM-assisted inference:**
- Business name when not explicit.
- Location inference from snippet (“Gwarimpa”, “Life Camp”, “Wuse”).
- Service evidence classification.
- Sentiment cue detection (“trusted”, “scam”, “no show”).

### 5.2.5 Looping policy (bounded exploration)
The agent loops based on what is missing.

**Gap types**
- Low candidate count
- Missing contacts
- Weak service match confidence
- Location ambiguity
- High spam/scam rate

**Refinement actions**
- Add “WhatsApp”, “phone number”, “call out” keywords.
- Add landmark / nearby variants.
- Add “recommended”, “reviews”, “trusted”.
- Prefer Maps if contacts are missing; prefer forum if trust is unclear.

### 5.2.6 Guardrails
- Hard cap tool calls: `max_tool_calls`
- Hard cap rounds: `max_rounds`
- Hard time budget
- Output must be strict JSON only.

---

## 5.3 Node 3 — Entity Resolution (Dedup)

### 5.3.1 Responsibilities
- Merge candidates referring to the same provider.

### 5.3.2 Matching strategy
**Primary key:** normalized phone number.
**Secondary keys:** normalized name + city + area.

### 5.3.3 ProviderProfile schema
```json
{
  "provider_id": "uuid",
  "name": "Kenny Plumbing Services",
  "phones": ["+2348012345678"],
  "location_city": "Abuja",
  "location_area": "Gwarimpa",
  "service_tags": ["plumbing"],
  "signals": {
    "mentions": 4,
    "sources": {"maps": 2, "web": 1, "forum": 1},
    "sentiment": {"pos": 3, "neg": 0, "neu": 1},
    "recency": "RECENT"
  },
  "evidence_bundle": [
    {"source": "maps", "url": "...", "snippet": "..."},
    {"source": "forum", "url": "...", "snippet": "..."}
  ]
}
```

---

## 5.4 Node 4 — Scoring & Ranking (Deterministic)

### 5.4.1 Why deterministic ranking
- Predictable outcomes.
- Easy tuning.
- Easy audits (“why did you recommend this?”).

### 5.4.2 Feature set
Core features:
- `service_match_confidence`
- `location_match_score`
- `contact_score` (has phone, WhatsApp if needed)
- `source_strength` (maps listings > random tweets, but configurable)
- `mention_count`
- `sentiment_score`
- `recency_score`
- `constraint_satisfaction` (WhatsApp-only, female provider, etc.)

### 5.4.3 Example scoring function
Let score be in [0, 1].

- **Service match:** 0.35
- **Location match:** 0.20
- **Contactability:** 0.15
- **Trust/sentiment:** 0.10
- **Recency:** 0.10
- **Evidence count/source diversity:** 0.10

Then apply penalties:
- Scam/red-flag penalty: -0.30 to -0.80 depending on severity
- Constraint violation: large penalty (e.g., WhatsApp-only but no WhatsApp)

### 5.4.4 Ranking output
Return Top 5 with:
- `final_score`
- `reason_codes` (machine-readable)
- `why_recommended` (short human line generated from reason codes)

---

## 5.5 Node 5 — Response Formatting

### 5.5.1 Provider card format
Each card should include:
- Name
- Phone + WhatsApp indicator
- Area/City
- “Why recommended” (1 line)
- Evidence sources (links)
- Optional: price signal, availability cue

### 5.5.2 Output examples
- “Recommended because: strong match for plumbing + Gwarimpa; WhatsApp contact available; recent positive mentions.”

---

## 6. Data & State Management

### 6.1 Minimal state (MVP)
Even if you don’t build a full database initially, you should support:
- Search session id
- SearchPlan snapshot
- Tool call logs (query, source, timestamp)
- Raw results (for replay)
- Extracted candidates and final ranking

### 6.2 Recommended storage model
- `search_sessions`
- `tool_calls`
- `raw_results`
- `candidates`
- `providers`
- `recommendations`
- `feedback`

This enables offline evaluation and iterative improvement.

---

## 7. Prompting & Output Contracts

### 7.1 Planner prompt design
- Strict JSON output.
- Include query diversification requirements.
- Include stop conditions.

### 7.2 Agent prompt design
- “You may call tools; your job is to return Candidate[] JSON.”
- Enforce:
  - tool-call budget,
  - evidence snippet required per candidate,
  - confidence fields,
  - no prose in final output.

### 7.3 Extraction prompt pattern
- Provide raw text
- Ask for structured extraction
- Require:
  - phones list,
  - best-guess name,
  - location hints,
  - service evidence,
  - confidence.

---

## 8. Evaluation & Testing

### 8.1 What to evaluate
- **Recall:** are there at least N candidates extracted for typical intents?
- **Precision:** are extracted candidates real service providers?
- **Contact correctness:** do phone numbers exist and normalize correctly?
- **Ranking quality:** do top 5 look sensible under constraints?

### 8.2 Test sets
Create a curated set of intents:
- 30–50 common service requests across major Nigerian cities
- Include slang/pidgin constraints

### 8.3 Replay-based evaluation
Store raw tool results and replay extraction/ranking to compare versions.

---

## 9. Safety, Abuse, and Scam Handling

### 9.1 Hard constraints
- No private/login scraping.
- Don’t return personally identifying info that is not already public business contact info.

### 9.2 Scam signals
- Excessive “pay first” cues
- Multiple complaints of fraud
- No traceable business identity + suspicious patterns

Apply rank penalties or exclusion depending on severity.

---

## 10. Observability

### 10.1 Essential logs
- Session id
- CanonicalIntent
- SearchPlan
- Tool calls (query, platform, duration)
- Candidate counts per round
- Stop condition reached
- Top 5 scores + reason codes

### 10.2 Metrics
- Average time to results
- Tool calls per request
- Candidates extracted per request
- % requests returning full 5

---

## 11. Deployment Notes

### 11.1 Runtime constraints
- Latency budget: 5–8 seconds (demo) with capped rounds.
- Token/cost budget: enforce tool-call caps and structured outputs.

### 11.2 Recommended stack (suggested)
- Backend: FastAPI (or similar)
- Task execution: async event loop
- Storage: SQLite/Postgres
- LLM: any tool-capable model with structured output support

---

## 12. API Design (Minimal)

### 12.1 /ai/recommend (single-shot)
**Request:** FormConfig JSON

**Response:**
- `recommendations`: Top5 cards
- `debug`: optional (search plan, counts, confidence)

### 12.2 /ai/recommend/debug (optional)
Returns:
- raw tool calls
- extracted candidates
- ranking breakdown

---

## 13. Implementation Checklist

### Phase 1 (AI-only MVP)
- [ ] Implement FormConfig + CanonicalIntent schema
- [ ] Node 1: Planner outputs SearchPlan JSON
- [ ] Node 2: Search+Extraction Agent returns Candidate[] JSON (bounded)
- [ ] Node 3: Dedup merges candidates into ProviderProfile[]
- [ ] Node 4: Deterministic scoring & ranking
- [ ] Node 5: Provider card formatter
- [ ] Logging for replay

### Phase 2 (Quality upgrades)
- [ ] Better synonym dictionary for Nigerian service terms
- [ ] Better scam handling
- [ ] Feedback loop to adjust ranking weights
- [ ] Offline evaluation suite

---

## 14. Appendix — Reference Enums

### 14.1 Urgency
- IMMEDIATELY
- TODAY
- THIS_WEEK
- NOT_URGENT

### 14.2 BudgetBand
- LOW
- MID
- HIGH
- NOT_SURE

### 14.3 Sentiment
- POSITIVE
- NEGATIVE
- NEUTRAL

### 14.4 Recency
- RECENT
- STALE
- UNKNOWN

---

## 15. Appendix — Example End-to-End Trace (Narrative)

1) User submits: “Electrician, Wuse 2 Abuja, urgent, mid budget, WhatsApp only, ‘my AC trips breaker’.”
2) Planner:
   - Normalizes: service might be *electrician* + *AC technician*.
   - Generates query sets emphasizing Maps + “WhatsApp” + “emergency”.
3) Agent round 1:
   - Runs maps/web queries.
   - Extracts 12 candidates; 7 with WhatsApp contacts.
4) Stop check fails (needs ≥ 20 candidates or ≥ 5 high-confidence).
5) Agent round 2:
   - Adds “AC repair electrician”, landmark variants, “reviews”.
   - Extracts 14 more, dedup → 20 total.
6) Dedup merges duplicates by phone.
7) Ranker picks top 5 by match, contactability, evidence diversity, and sentiment.
8) Formatter returns 5 cards with evidence links.

