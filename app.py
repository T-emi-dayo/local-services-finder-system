"""
Local Services Finder - FastAPI Backend

POST /api/search          → start async job, returns job_id
GET  /api/status/{job_id} → poll job status and result
GET  /                    → serve frontend (via StaticFiles)
"""

import asyncio
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agent.graph import run_agent
from src.models.FormConfig import FormConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

# In-memory job store
jobs: Dict[str, Dict[str, Any]] = {}

app = FastAPI(title="Local Services Finder API", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(FormConfig):
    mock: bool = False


MOCK_RESULT = {
    "summary": (
        "Found 3 verified plumbers in Lekki, Lagos. All providers have confirmed contact numbers "
        "and are experienced with residential plumbing. Emeka Plumbing Works is ranked first for "
        "strong review history and competitive pricing. AquaFix Nigeria edges out the third slot "
        "due to faster stated response times."
    ),
    "sources": ["Google Maps", "Local Business Directory"],
    "candidates": [
        {
            "name": "Emeka Plumbing Works",
            "phones": ["+234 803 421 7865", "+234 901 234 5678"],
            "whatsapp_number": "2348034217865",
            "location": "Lekki Phase 1, Lagos",
            "service_tags": ["Plumbing", "Pipe Repair", "Burst Pipe", "Leakage Fix", "Bathroom Fitting"],
            "price_signal": "LOW",
            "source": "Google Maps",
            "business_id": None,
            "website": None,
            "email": None,
            "rating": 4.6,
            "reviews_summary": "Customers praise fast arrival times and transparent pricing. Several reviews mention same-day resolution for burst pipes.",
            "evidence": (
                "Ranked #1. Highest completeness score with 5 contact fields filled. "
                "Price signal (LOW) aligns with stated budget. Service tags directly match 'plumber' request. "
                "Lekki Phase 1 location is an exact area match. Review summary indicates strong reliability."
            ),
        },
        {
            "name": "Swift Plumb Lagos",
            "phones": ["+234 812 900 3341"],
            "whatsapp_number": "2348129003341",
            "location": "Lekki / Ajah Axis, Lagos",
            "service_tags": ["Plumbing", "Drainage Clearing", "Water Heater Installation", "Tank Repair"],
            "price_signal": "MID",
            "source": "Google Maps",
            "business_id": None,
            "website": None,
            "email": None,
            "rating": 4.2,
            "reviews_summary": "Reliable for scheduled jobs. A few reviews note slightly higher rates than local alternatives, but workmanship is consistently praised.",
            "evidence": (
                "Ranked #2. Good completeness with WhatsApp contact available. "
                "MID price signal is within acceptable range for the stated budget. "
                "Service tags cover drainage and tank work which are common co-needs with plumbing. "
                "Location covers the Lekki/Ajah corridor — acceptable proximity."
            ),
        },
        {
            "name": "AquaFix Nigeria Ltd",
            "phones": ["+234 706 118 4422", "+234 802 554 9900"],
            "whatsapp_number": None,
            "location": "Victoria Island / Lekki, Lagos",
            "service_tags": ["Plumbing", "Pipe Installation", "Commercial Plumbing", "Emergency Callout"],
            "price_signal": "MID",
            "source": "Local Business Directory",
            "business_id": None,
            "website": None,
            "email": "aquafix.ng@gmail.com",
            "rating": 4.0,
            "reviews_summary": "Best suited for urgent callouts. Operates across VI and Lekki. Slightly longer response times reported on weekends.",
            "evidence": (
                "Ranked #3. Two phone numbers with email contact increases reachability. "
                "Emergency callout tag is relevant for IMMEDIATELY urgency requests. "
                "Covers both Lekki and VI, slightly wider area than the target but acceptable. "
                "No WhatsApp listed reduces convenience score marginally."
            ),
        },
    ],
}


@app.post("/api/search")
async def start_search(request: SearchRequest):
    job_id = str(uuid.uuid4())

    if request.mock:
        jobs[job_id] = {"status": "done", "result": MOCK_RESULT}
        return {"job_id": job_id}

    jobs[job_id] = {"status": "running"}
    config = FormConfig(**request.model_dump(exclude={"mock"}))
    asyncio.create_task(_run_search(job_id, config))
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _run_search(job_id: str, config: FormConfig):
    try:
        result = await asyncio.to_thread(run_agent, config)

        candidates = []
        for c in result.get("final_candidates", []):
            candidates.append(c.model_dump() if hasattr(c, "model_dump") else c)

        jobs[job_id] = {
            "status": "done",
            "result": {
                "candidates": candidates,
                "summary": result.get("summary", ""),
                "sources": result.get("sources", []),
            },
        }
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        jobs[job_id] = {"status": "error", "error": str(e)}


# Must be last — mounts frontend as catch-all so API routes take priority
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="spa")
