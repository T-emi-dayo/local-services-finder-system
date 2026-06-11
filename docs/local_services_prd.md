# Local Service Finder AI Chatbot – Product Requirements Document (PRD)

---

## 1. Overview

The Local Service Finder AI Chatbot is an intelligent conversational system designed to help users in Nigeria quickly locate reliable service providers (e.g., AC repairers, plumbers, electricians, mechanics). Users interact with a friendly Nigerian-aware chatbot that asks key questions, searches multiple online sources, extracts real businesses, ranks them, and returns a curated list of recommended providers with contact details.

The system supports English, Pidgin, Nigerian shorthand, and slang. It is designed to be usable even by elderly people or users unfamiliar with technology.

---

## 2. Objectives

- Provide fast, accurate recommendations of service providers based on user needs.
- Support natural, conversational interaction while grounding the search with a structured form.
- Search multiple online platforms and extract real service providers.
- Rank providers based on relevance, reputation, sentiment, and requirements.
- Return clear, contact-ready provider cards (up to 5 per search).
- Keep the system Nigeria-focused with contextual language intelligence.

---

## 3. Users & Personas

### Primary User
Everyday person in Nigeria looking for a service provider.

Characteristics:
- May have limited tech experience.
- May prefer Pidgin or slang.
- Wants quick, direct answers.
- Needs providers they can trust and contact immediately.

### Secondary User
Younger or more tech-savvy Nigerians.

### Tertiary User (Future)
Internal operations team validating providers or reviewing feedback.

---

## 4. System Capabilities (High-Level)

- Conversational interface (chatbot).
- Initial structured form to gather essential search data.
- AI-powered query understanding (English, Pidgin, shorthand).
- Multi-platform search (Google, Google Maps, Twitter/X, Nairaland).
- NLP-based extraction of businesses from online text.
- Sentiment analysis for mentions.
- Ranking engine that returns up to 5 best-fit providers.
- Elder-friendly output format.
- Optional user feedback on recommendations.

---

## 5. Chatbot Behavior

### Tone & Style
- Friendly Nigerian tone.
- Clear and simple English when needed.
- Short messages.
- Avoids jargon and over-explanation.

### Behavior Rules
- Always confirm what the user wants before searching.
- Ask follow-up questions only when necessary.
- Request any missing essential data.
- Provide reassurance during search (e.g., “Make I quickly check Google and Nairaland”).
- Present results in a simple, card-like format.

---

## 6. Conversation Flow

### Step 1 — Initial Structured Form
Mandatory fields:
- Service type
- Location (Area + City)
- Urgency (Not urgent / Today / Immediately)
- Budget (Low / Medium / High / Not sure)

### Step 2 — Extra Requirements (Optional)
User may specify:
- Price preference
- Gender preference
- Instructions or constraints
- Additional requirements

### Step 3 — Chatbot Confirmation
The chatbot repeats the user's interpreted request and asks for permission to start searching.

### Step 4 — Search Execution
The bot searches all selected platforms using:
- LLM-optimized query rewriting
- Automated scraping or APIs

### Step 5 — Recommendations (Top 5)
Bot returns contact-ready provider cards.

### Step 6 — Follow-up Conversation
User may refine:
- “Show cheaper options”
- “Find someone closer”
- “Is there somebody available now?”

### Step 7 — Feedback (Optional)
User may label a provider as:
- Good
- Bad
- Scam
- Not available

---

## 7. Search Intent Schema

### Essential Fields
- service_type  
- location_area  
- location_city  
- urgency  
- budget  

### Optional Fields
- gender preference
- reliability requirement
- price sensitivity
- proximity preference
- WhatsApp-only requirement
- Safety preferences

### Language Capabilities
The system must understand:
- English
- Nigerian Pidgin
- Mixed code-switching
- Slang and shorthand

---

## 8. Data Sources (v1)

### Selected Sources
- Google Search
- Google Maps
- Twitter/X
- Nairaland

### Reasons for Selection
- High Nigerian relevance
- Publicly accessible
- Good volume of provider mentions
- Low technical overhead compared to Instagram/Facebook

---

## 9. Extraction Engine

The system must extract from raw text:
- Business name
- Phone numbers (Nigerian format)
- Location or landmarks
- Service type
- Price indicators
- Sentiment cues
- Recency of posts
- Social links (if provided)

### Techniques
- Regex + heuristics
- NLP pipelines
- LLM extraction for ambiguity

---

## 10. Ranking Engine

### No Categories in v1
The system returns one simple ranked list of the top 5 providers.

### Ranking Signals
- Match to service type
- Match to location
- Mention frequency
- Sentiment score
- Recency of mentions
- Contact availability
- Match to user extra requirements

### Priority
User intent is always the strongest weight.

---

## 11. Provider Output Format (v1)

Each provider card includes:
- Business Name  
- Location  
- Phone Number  
- WhatsApp (if available)  
- Pricing Signal (cheap/medium/premium/unknown)  
- Short Sentiment Summary  
- “Why Recommended” reasoning  
- Source List (e.g., Google 3, Nairaland 2)

Bot returns **5 providers**.

---

## 12. Feedback Loop (Optional for MVP)

User feedback types:
- Good
- Bad
- Not available
- Scam

### Purpose
- Improve ranking
- Train heuristics
- Build long-term trust and accuracy

---

## 13. Non-Functional Requirements

### Latency
- Target ≤ 5 seconds.
- If slower, bot gives status updates.

### Reliability
- Must avoid breaking if one source is down.

### Security
- No scraping of private or login-required data.

### Logging
Track:
- Searches
- Errors
- Extracted providers
- User feedback

### Scalability
Should support thousands of daily searches.

---

## 14. System Architecture (High-Level)

### Frontend
- Structured form
- Chat interface

### Backend
- Chat and conversation manager
- Search intent interpreter
- Search orchestrator
- Extraction engine
- Ranking engine
- Provider formatter
- Feedback handler

### LLM Layer
- Query parsing
- Data extraction
- Sentiment analysis
- Recommendation reasoning

### Database
- Provider Store
- Mentions Store
- Feedback Table
- Search Logs

---

## 15. Roadmap (Milestones)

### Milestone 1 — Intent Capture + Form
- Implement form UX
- LLM parsing
- Confirmation flow

### Milestone 2 — Search Integration
- Google Search
- Google Maps
- Twitter/X
- Nairaland

### Milestone 3 — Extraction Layer
- Regex + NLP extraction
- Name/location/contact parsing

### Milestone 4 — Ranking Engine
- Relevance scoring
- Sentiment integration

### Milestone 5 — Recommendation Cards
- Format
- Explanation
- Source list

### Milestone 6 — Feedback System
- Thumbs up/down
- Feedback logging

### Milestone 7 — Optimization
- Faster extraction
- Stronger Pidgin parsing
- Better price inference

---