# Local Services Finder (LSF)

An AI-powered recommendation system that helps Nigerians find local service providers (plumbers, electricians, mechanics, etc.). A user submits a short form; a LangGraph pipeline resolves the real service need, searches local business data, enriches and cleans the candidates, and returns a ranked list with contact details and a short explanation for each pick.

> **Status:** working proof of concept. Data coverage is the main limitation: informal artisans are largely absent from accessible sources. See [docs/Major_blockages_in_project_completion.md](docs/Major_blockages_in_project_completion.md).

## How it works

```
FormConfig -> resolve_intent -> orchestrate_tools -> cleanup -> rank_and_synthesize -> results
                                      |                                ^
                                      +-- no candidates (not_found) ---+
```

| Node | File | Type | Role |
|---|---|---|---|
| Intent resolution | `src/agent/nodes/IntentResolutionNode.py` | LLM | Corrects the service type using `additional_details` and generates primary (area) and fallback (city) search params. Falls back to raw form values if the LLM fails. |
| Tool orchestration | `src/agent/nodes/ToolOrchestrationNode.py` | Programmatic | Tier 1: local business search with fallback and relaxed retries. Tier 2: details and reviews enrichment for the best candidates. |
| Cleanup | `src/agent/nodes/CleanupNode.py` | Mixed | Completeness ranking, then LLM logical validation, then LLM semantic dedup. LLM steps pass through on failure. |
| Ranking and synthesis | `src/agent/nodes/RankingSynthesisNode.py` | LLM | Ranks against explicit criteria, writes per-candidate evidence and a summary. Uses a deterministic ranking if the LLM fails. Always the terminal node. |

Full design: [docs/ai_system_architecture_design.md](docs/ai_system_architecture_design.md).

## Project layout

```
app.py                  FastAPI backend (serves the frontend and the job API)
frontend/index.html     Single-file UI
core/                   Config loader (config.py) and model/prompt settings (config.yaml)
src/agent/              LangGraph graph, state, and nodes
src/models/             Pydantic schemas (FormConfig, RawCandidate, IntentAndSearchParams)
src/tools/              Business search, details, and reviews tools (RapidAPI), plus other tools not wired in
utils/llm_helper.py     OpenAI client helpers
docs/                   Architecture, PRD, tooling notes
tests/, test_tools.py   Manual test scripts
```

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/) (a `uv.lock` is included).

```bash
uv sync
```

Create a `.env` file in the project root:

```
OPENAI_API_KEY=...   # required, validated on startup
RAPID_API_KEY=...    # RapidAPI key for the Local Business Search API
```

Models and temperatures are set in `core/config.yaml` (default `gpt-4o-mini`).

## Running

```bash
uv run uvicorn app:app --reload
```

Open http://localhost:8000 for the UI, or http://localhost:8000/docs for the Swagger UI.

### API

| Endpoint | Method | Description |
|---|---|---|
| `/api/search` | POST | Body is a `FormConfig` (plus optional `"mock": true`). Returns `{"job_id": "..."}`. |
| `/api/status/{job_id}` | GET | Returns `{status, result?, error?}`. `status` is `running`, `done`, or `error`. |

`FormConfig` fields: `service_type`, `location_city`, `location_area`, `urgency` (`IMMEDIATELY`, `TODAY`, `THIS_WEEK`, `NOT_URGENT`), `budget` (`LOW`, `MEDIUM`, `HIGH`, `NO_BUDGET`), `additional_details` (optional).

Example:

```bash
curl -X POST localhost:8000/api/search -H "Content-Type: application/json" \
  -d '{"service_type":"Plumber","location_city":"Lagos","location_area":"Lekki","urgency":"TODAY","budget":"MEDIUM","additional_details":"Burst pipe in the kitchen"}'
```

Use `"mock": true` to get a canned result without calling any external service. Jobs are stored in memory and are lost on restart.

### Running the agent directly

```bash
python -m tests.test_extraction_agent
```

`python -m tests.test_tools` (run from the project root) dumps raw responses from the three RapidAPI tools, which is useful when checking field mapping.

## Known limitations

- Only formal businesses with a web or map presence are discoverable.
- Job storage is an in-memory dict.
- Several files in `tests/` target removed modules (`QueryPlanner`, `ExtractionAgent`, `data_enrichment_tool`) and no longer run.
- `map_search_tool`, `web_search_tool`, and `web_scrapping_tool` exist in `src/tools/` but are not used by the graph.

## Documentation

- [Architecture and design](docs/ai_system_architecture_design.md)
- [Product requirements (original)](docs/local_services_prd.md)
- [Tooling notes](docs/tools.md) and [tooling strategy](docs/initial_llm_tools.md)
- [Major blockages](docs/Major_blockages_in_project_completion.md)
- [Development rules](docs/RULE.md)
