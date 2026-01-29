# Local Services Finder — Tooling Strategy (Without Nairaland)

## Purpose of This Document

This document explains, in **conceptual and architectural terms**, the tools and data sources selected for the **Local Services Finder system**, **excluding Nairaland**.  
The focus is on **why each tool exists**, **what problem it solves**, **what kind of data it contributes**, and **how it fits into the overall system**, not implementation details.

The goal is to **solve the discovery problem reliably**, not to scrape everything that exists.

---

## Core Problem Being Solved

Users want to find **reliable local service providers in Nigeria** (plumbers, electricians, mechanics, etc.) with:

- Correct contact information
- Location relevance
- Proof of legitimacy or community trust
- WhatsApp availability (critical in Nigeria)
- Emergency or informal options when needed

The challenge is that **no single data source covers all of this well**.

---

## High-Level Strategy

Instead of scraping one difficult forum (Nairaland), the system uses a **multi-source, weighted approach**:

1. **Verified business sources** (accuracy)
2. **Nigerian-specific directories** (local relevance)
3. **Community recommendations via APIs** (trust)
4. **LLM-powered extraction as a fallback** (coverage)

Each tool contributes **different strengths**, and weaknesses are compensated by others.

---

## Tool Category 1: Map-Based Search Tools

### 1. Google Maps Search Tool

**What problem it solves**
- Finds **verified, registered businesses**
- Provides ratings, reviews, phone numbers, addresses
- Strong for established services

**Why it is important**
- Highest data accuracy
- Built-in trust signals (reviews, ratings)
- Best geolocation precision

**Limitations**
- Requires API key
- Misses informal providers
- WhatsApp-only businesses may not appear
- Smaller towns may have weak coverage

**Role in the system**
- Primary data source when available
- Carries high weight in ranking (trust factor)

---

### 2. OpenStreetMap (OSM) Search Tool

**What problem it solves**
- Provides a **free fallback** to Google Maps
- Ensures the system never fails due to missing API keys

**Why it is important**
- No API key required
- Community-maintained data
- Works nationwide

**Limitations**
- Fewer reviews
- Less consistent phone numbers
- Data freshness varies

**Role in the system**
- Fallback map provider
- Used automatically when Google Maps is unavailable
- Ensures resilience and continuity

---

## Tool Category 2: Nigerian Business Directories

### Why Directories Matter More Than Forums

Directories are **designed to expose business data**:
- Structured listings
- Explicit phone numbers
- Service categories
- Clear locations

This makes them **far more reliable than forum posts** for service discovery.

---

### 3. Vconnect Directory Tool

**What problem it solves**
- Finds **Nigerian-registered businesses**
- Strong coverage for professional services

**Strengths**
- Structured listings
- Clear contact details
- Categories match Nigerian market reality
- Easier to maintain than forums

**Limitations**
- Mostly formal businesses
- Less coverage for informal or emergency providers

**Role in the system**
- Core Nigerian business source
- Balances Google Maps with local context
- Medium-to-high trust weight

---

### 4. Jiji Services Tool

**What problem it solves**
- Captures **informal service providers**
- Finds freelancers, artisans, emergency workers

**Why it is critical**
- Nigeria has a large informal economy
- Many trusted providers operate outside formal directories

**Strengths**
- Direct phone numbers
- WhatsApp availability common
- Pricing information often included
- Covers individuals and small operators

**Limitations**
- Less verification
- Higher noise
- Duplicate listings possible

**Role in the system**
- Informal service coverage
- Emergency and budget scenarios
- Deduplication required downstream

---

## Tool Category 3: Social & Community APIs (No Scraping)

### Why APIs Beat Forum Scraping

- Stable
- Structured JSON responses
- Clear rate limits
- Legal and predictable
- Easier long-term maintenance

---

### 5. Reddit Nigeria Search Tool

**What problem it solves**
- Finds **community recommendations**
- Captures warnings, praise, and trust signals

**Why Reddit works**
- Nigerians actively recommend services
- Honest feedback
- Searchable history

**Strengths**
- Official API
- Comments provide rich context
- Good for sentiment and reputation

**Limitations**
- Not all providers are mentioned
- Extraction needed to identify contacts

**Role in the system**
- Trust validation layer
- Reputation boost or penalty
- Community-based ranking input

---

### 6. Twitter/X Nigeria Search Tool (Optional)

**What problem it solves**
- Real-time service mentions
- Urgent complaints or praise

**Strengths**
- Fast signal
- Trend detection
- Crisis or emergency insights

**Limitations**
- API access cost
- High noise
- Short-form content

**Role in the system**
- Optional real-time signal
- Low-to-medium weight
- Useful for emergencies

---

### 7. Telegram Groups (Optional)

**What problem it solves**
- Hyper-local service discovery
- Informal provider networks

**Strengths**
- Strong Nigerian adoption
- Real conversations
- Direct contacts

**Limitations**
- Fragmented data
- Harder moderation
- Requires careful extraction

**Role in the system**
- Advanced / optional expansion
- Informal trust network

---

## Tool Category 4: Validation & Enrichment Tools

### 8. Phone Validation Tool

**What problem it solves**
- Deduplicates providers
- Normalizes phone numbers
- Identifies Nigerian carriers
- Determines WhatsApp compatibility

**Why it is critical**
- Phone number is the strongest identifier
- Nigerian numbers appear in many formats
- Prevents duplicate results

**Role in the system**
- Mandatory preprocessing step
- Foundation for deduplication

---

### 9. WhatsApp Business Verification Tool

**What problem it solves**
- Confirms WhatsApp availability
- Identifies business vs personal accounts
- Improves accessibility scoring

**Why it matters in Nigeria**
- WhatsApp is the primary business channel
- Many users prefer WhatsApp-only providers

**Role in the system**
- Accessibility filter
- Ranking boost when required by user

---

## Tool Category 5: LLM-Powered Web Search (Fallback Strategy)

### 10. LLM Web Search & Extraction Tool

**What problem it solves**
- Handles sites that are hard to scrape
- Extracts structured data from unstructured text
- Eliminates custom scraper maintenance

**How it works conceptually**
1. Search the web for relevant pages
2. Fetch page content
3. Ask LLM to extract provider data
4. Normalize into system schema

**Strengths**
- Works on any site
- Resilient to layout changes
- No site-specific logic

**Limitations**
- Higher cost
- Requires careful prompt design
- Needs validation layer

**Role in the system**
- Last-resort coverage
- Handles edge cases
- Complements structured tools

---

## Final Recommended Tool Stack (No Nairaland)

### Core (Always On)
- Google Maps (if API key)
- OpenStreetMap
- Vconnect
- Jiji
- Phone Validation
- WhatsApp Verification

### Trust & Community
- Reddit Nigeria API

### Optional Enhancements
- Twitter/X
- Telegram
- LLM Web Search

---

## Why This Is Better Than Nairaland Scraping

- 80% less complexity
- Fewer failures
- Better data quality
- Clear legal boundaries
- Easier scaling
- Long-term maintainability

---

## Bottom Line

The system shifts from **“scrape everything”** to **“combine the right signals”**.

This approach:
- Solves the real Nigerian service discovery problem
- Avoids brittle scraping
- Prioritizes reliability, trust, and usability

This is the correct architectural direction.
