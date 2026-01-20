# Local Service Finder AI Chatbot – Task Breakdown

Below is an implementation-focused task list derived directly from the PRD.

---

## 0. Project Setup & Foundations

- [ ] Create repository (`local-service-finder-chatbot` or similar)
- [ ] Set up Python environment (Poetry/pipenv/requirements.txt)
- [ ] Choose core stack:
  - [ ] Backend framework (FastAPI / Django REST / similar)
  - [ ] LLM provider SDK (OpenAI / etc.)
- [ ] Add core dependencies:
  - [ ] HTTP client (httpx/requests)
  - [ ] Async support (if needed)
  - [ ] DB ORM (SQLAlchemy / Prisma / etc.)
  - [ ] Logging (structlog / standard logging)
  - [ ] Task queue (optional, for long searches)
- [ ] Configure `.env` and config layer for:
  - [ ] LLM API keys
  - [ ] DB URL
  - [ ] External API credentials (if any)
- [ ] Set up basic CI:
  - [ ] Linting (ruff/flake8/black)
  - [ ] Tests runner
  - [ ] Pre-commit hooks (optional)

---

## 1. Data Model & Database

- [ ] Design and implement database schema:
  - [ ] `businesses` table
    - [ ] id, name, normalized_name
    - [ ] service_type
    - [ ] location_area, location_city
    - [ ] phone_number, whatsapp_number
    - [ ] price_level (cheap/medium/premium/unknown)
    - [ ] created_at, updated_at
  - [ ] `mentions` table
    - [ ] id, business_id
    - [ ] source (google, maps, twitter, nairaland)
    - [ ] url
    - [ ] content_snippet
    - [ ] sentiment_score
    - [ ] sentiment_label
    - [ ] posted_at
  - [ ] `search_logs` table
    - [ ] id, user_id (nullable for MVP)
    - [ ] raw_query
    - [ ] parsed_intent (JSON)
    - [ ] result_count
    - [ ] created_at
  - [ ] `feedback` table
    - [ ] id, business_id, search_id
    - [ ] label (good/bad/scam/not_available)
    - [ ] comment (optional)
    - [ ] created_at
- [ ] Implement ORM models & migrations
- [ ] Add indices:
  - [ ] `normalized_name`
  - [ ] `service_type + location_city`
  - [ ] `business_id` in `mentions`
- [ ] Seed DB with a few test businesses and mentions

---

## 2. Frontend – Form + Chat UX (Even if simple)

> Can be web-only for MVP (e.g., simple React or basic HTML + JS).

- [ ] Implement initial **structured form**:
  - [ ] Field: Service type (dropdown + free text)
  - [ ] Field: Location (Area)
  - [ ] Field: City (dropdown or free text)
  - [ ] Field: Urgency (Not urgent / Today / Immediately)
  - [ ] Field: Budget (Low / Medium / High / Not sure)
  - [ ] Field: Extra requirements (textarea)
- [ ] Implement **chat interface**:
  - [ ] Chat message history view
  - [ ] Input box for user replies
  - [ ] Bot messages styled distinctly
- [ ] Implement flow:
  - [ ] Submit form → send payload to backend
  - [ ] Show chatbot confirmation message
  - [ ] “Yes, start search” button
  - [ ] Display streaming or batched responses from backend

---

## 3. Conversation Orchestrator (Backend)

- [ ] Implement `/conversation/start` endpoint:
  - [ ] Accepts form data (service, location, urgency, budget, extra_req)
  - [ ] Builds initial **Search Intent object**
- [ ] Implement `/conversation/confirm_and_search` endpoint:
  - [ ] Accepts intent id or payload
  - [ ] Triggers search pipeline
- [ ] Conversation manager:
  - [ ] Takes intent
  - [ ] Generates confirmation message using LLM template
  - [ ] Handles user confirmation / correction
- [ ] Add simple session mechanism:
  - [ ] Link session id ↔ search intent
  - [ ] Store basic state (e.g., last intent, last results)

---

## 4. LLM – Query Understanding & Intent Parsing

- [ ] Define **Search Intent Schema** (Python model / pydantic):
  - [ ] service_type
  - [ ] location_area
  - [ ] location_city
  - [ ] urgency
  - [ ] budget
  - [ ] extra_requirements (list or string)
- [ ] Design prompt for **language understanding**:
  - [ ] Handles English, Pidgin, slang, shorthand
  - [ ] Explicitly tailored for Nigerian context
- [ ] Implement function:
  - [ ] `parse_free_text_to_intent(raw_text) -> SearchIntent`
- [ ] Add examples in prompt:
  - [ ] “I need AC guy for Lekki now now”
  - [ ] “Plumber wey no too cost for Wuse”
  - [ ] “Mechanic for Agege, cheap one”
- [ ] Add unit tests for parsing:
  - [ ] 15–30 test cases for Nigerian-style inputs

---

## 5. External Search Integrations

### 5.1 Search Orchestrator

- [ ] Define interface `SourceClient`:
  - [ ] `search(intent: SearchIntent) -> list[RawResult]`
- [ ] Implement central orchestrator:
  - [ ] Takes `SearchIntent`
  - [ ] Dispatches to all enabled source clients (async if possible)
  - [ ] Collects and merges `RawResult` lists

### 5.2 Google Search Client

- [ ] Decide on method:
  - [ ] Custom Search API or scraping
- [ ] Implement:
  - [ ] Build search query from `service_type + location_city + area`
  - [ ] Call Google API
  - [ ] Parse titles, snippets, URLs to `RawResult`

### 5.3 Google Maps Client

- [ ] Implement:
  - [ ] Place search for service type in location
  - [ ] Fetch:
    - [ ] Business name
    - [ ] Address
    - [ ] Rating (if available)
    - [ ] Phone number
  - [ ] Normalize to `RawResult`

### 5.4 Twitter/X Client

- [ ] Decide: official API vs scraping (depends on access)
- [ ] Implement:
  - [ ] Build query with service + location keywords
  - [ ] Fetch relevant tweets
  - [ ] Extract:
    - [ ] Tweet text
    - [ ] Links
    - [ ] Mentioned business names / contacts

### 5.5 Nairaland Client

- [ ] Implement scraper:
  - [ ] Thread search by keywords
  - [ ] Parse posts:
    - [ ] Text content
    - [ ] Contact info
    - [ ] Business names / area
  - [ ] Return as `RawResult`

---

## 6. Extraction & Normalization

- [ ] Define `RawResult` schema:
  - [ ] source
  - [ ] title
  - [ ] snippet
  - [ ] url
  - [ ] raw_text
  - [ ] timestamp (if available)
- [ ] Implement extractor functions:
  - [ ] `extract_business_name(raw: RawResult)`
  - [ ] `extract_phone_numbers(text)`
  - [ ] `extract_location(text)`
  - [ ] `infer_service_type(text, intent)`
- [ ] Implement Nigerian phone regex + normalizer:
  - [ ] +234/0 prefixes
  - [ ] 070/080/081/090 etc.
- [ ] Upsert logic:
  - [ ] Normalize business name (lowercase + stripped)
  - [ ] Find existing business by normalized name + city
  - [ ] If exists → attach new `mention`
  - [ ] Else → create new `business` + `mention`
- [ ] Add tests with realistic sample texts from each source

---

## 7. Sentiment & Signal Computation

- [ ] Define sentiment categories:
  - [ ] positive / neutral / negative
- [ ] Design sentiment prompt (Nigeria-aware):
  - [ ] Understands slang: “guy sabi work”, “no try am”, “scam o”
- [ ] Implement:
  - [ ] `analyze_sentiment(text) -> {label, score}`
- [ ] Compute **per-mention** scores:
  - [ ] Save to `mentions.sentiment_score` and `sentiment_label`
- [ ] Implement **per-business aggregation**:
  - [ ] Average sentiment
  - [ ] Recent mentions weight higher
  - [ ] Count of positive / negative mentions
- [ ] Add heuristics to detect:
  - [ ] Red flags (scam, no show, insult, overcharge, harassment)
  - [ ] Speed (“quick”, “delay”, etc.)
  - [ ] Price (“cheap”, “too cost”, “expensive”)

---

## 8. Ranking Engine

- [ ] Define ranking model:
  - [ ] Base score from:
    - [ ] sentiment aggregate
    - [ ] mention count (log-scaled)
    - [ ] recency factor
    - [ ] contact availability
  - [ ] Adjust with user intent:
    - [ ] Extra requirements like “cheap” or “fast”
- [ ] Implement:
  - [ ] `rank_businesses(candidates, intent) -> list[RankedBusiness]`
- [ ] Ensure:
  - [ ] Only businesses matching service + location strongly considered
- [ ] Add tests:
  - [ ] Synthetic data to check ordering:
    - [ ] High sentiment vs low sentiment
    - [ ] Recent vs old mentions
    - [ ] With vs without contact info

---

## 9. Recommendation Explanation (“Why Recommended”)

- [ ] Design LLM prompt for **short explanation**:
  - [ ] Nigerian tone
  - [ ] Max 1–2 sentences
- [ ] Input to LLM:
  - [ ] Business stats (sentiment, mentions, recency)
  - [ ] Sources (counts per platform)
  - [ ] Key keywords (“cheap”, “fast”, etc.)
- [ ] Output examples:
  - [ ] “People for Gwarinpa dey talk say him dey show quick and him price no too high.”
  - [ ] “Many recent comments say her work neat and she dey pick call.”
- [ ] Implement:
  - [ ] `generate_reasoning(business_summary, intent) -> str`
- [ ] Cache reasoning per business + intent combination when possible

---

## 10. API for Recommendations

- [ ] Implement `/search` endpoint:
  - [ ] Input: SearchIntent + optional extra requirements
  - [ ] Pipeline:
    - [ ] Log request
    - [ ] Call search orchestrator
    - [ ] Extract + normalize + upsert DB
    - [ ] Aggregate signals
    - [ ] Rank businesses
    - [ ] Generate reasoning
    - [ ] Return top 5 as DTO
- [ ] Define response DTO:
  - [ ] name
  - [ ] location_area
  - [ ] location_city
  - [ ] phone_number
  - [ ] whatsapp_number
  - [ ] price_level
  - [ ] sentiment_summary
  - [ ] why_recommended
  - [ ] sources_summary

---

## 11. Feedback Handling

- [ ] Implement `/feedback` endpoint:
  - [ ] Input: { search_id, business_id, label, comment? }
  - [ ] Save record to `feedback`
- [ ] Update business scoring (later phase):
  - [ ] Adjust ranking if many “bad” or “scam” flags
- [ ] Add light rate limiting to avoid spam feedback

---

## 12. Logging, Monitoring & Error Handling

- [ ] Implement structured logging:
  - [ ] Each search pipeline run
  - [ ] Each external source call
  - [ ] Errors/exceptions
- [ ] Add metrics (even if basic):
  - [ ] Number of searches per day
  - [ ] Average time per search
  - [ ] External source failures
- [ ] Implement fallback behavior:
  - [ ] If some sources fail, still return partial results
  - [ ] Log but don’t crash

---

## 13. Non-Functional & Ops

- [ ] Add config for:
  - [ ] API timeouts to each source
  - [ ] Max LLM calls per search
- [ ] Add simple health check endpoint:
  - [ ] `/health` returns service status
- [ ] Deployment basics:
  - [ ] Dockerfile
  - [ ] Environment configuration for dev/staging/prod
- [ ] Test performance:
  - [ ] Time from “start search” to results return
  - [ ] Aim for ≤ 5 seconds for common cases

---

## 14. Polishing & UX Iteration

- [ ] Refine bot tone:
  - [ ] Mix of English + light Pidgin
  - [ ] Ensure clarity for elderly users
- [ ] Add small touches:
  - [ ] “Searching Google and Nairaland for you, hold on small.”
  - [ ] Retry prompt if user gives unclear feedback
- [ ] Collect real user queries and:
  - [ ] Expand parsing examples
  - [ ] Improve extraction patterns
  - [ ] Adjust ranking weights

---