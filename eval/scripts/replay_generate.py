"""Generate responses from a frozen SQLite corpus; this script never calls RapidAPI."""
import argparse
import json
import re
import sys
from pathlib import Path

from common import DATA, connect, jsonl_read, jsonl_write
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import src.agent.nodes.IntentResolutionNode as intent_node
import src.agent.nodes.CleanupNode as cleanup_node
import src.agent.nodes.RankingSynthesisNode as ranking_node
from llm_cache import cached_call_structured_llm

intent_node.call_structured_llm = cached_call_structured_llm
cleanup_node.call_structured_llm = cached_call_structured_llm
ranking_node.call_structured_llm = cached_call_structured_llm
from src.agent.nodes.CleanupNode import cleanup
from src.agent.nodes.IntentResolutionNode import resolve_intent
from src.agent.nodes.RankingSynthesisNode import rank_and_synthesize
from src.agent.state import AgentState
from src.models.FormConfig import FormConfig
from src.models.RawCandidate import RawCandidate


def local_candidates(db, query, resolved_service, limit=10):
    tokens = re.findall(r"[A-Za-z0-9]+", f"{resolved_service} {query['location_area']} {query['location_city']}")
    match = " OR ".join('"' + t.replace('"', '') + '"' for t in tokens if len(t) > 1)
    rows = []
    if match:
        try:
            rows = db.execute("""SELECT p.* FROM providers_fts f JOIN providers p ON p.id=f.rowid
                WHERE providers_fts MATCH ? ORDER BY bm25(providers_fts) LIMIT 100""", (match,)).fetchall()
        except Exception:
            rows = []
    service = resolved_service.casefold()
    area = query["location_area"].casefold()
    city = query["location_city"].casefold()
    service_terms = [t for t in re.findall(r"[a-z0-9]+", service) if len(t) > 2]
    rows = [r for r in rows if any(t in f"{r['category'] or ''} {r['name']}".casefold() for t in service_terms)]
    def score(r):
        return (3 * (service in (r["category"] or "").casefold())
                + 2 * (area in (r["area"] or "").casefold())
                + (city in (r["city"] or "").casefold())
                + (r["phone"] not in (None, "")) + (r["rating"] or 0) / 5)
    rows = sorted(rows, key=score, reverse=True)[:limit]
    return [RawCandidate(name=r["name"], phones=[r["phone"]] if r["phone"] else [],
                         location=r["address"] or f"{r['area']}, {r['city']}",
                         service_tags=[x.strip() for x in (r["category"] or "").split(",") if x.strip()],
                         rating=r["rating"], business_id=r["provider_key"],
                         source=f"frozen:{r['source']}") for r in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries", help="Golden/test JSONL")
    parser.add_argument("--db", default=str(DATA / "corpus.sqlite"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    queries = jsonl_read(args.queries)
    db = connect(args.db)
    results = []
    for index, query in enumerate(queries, 1):
        config = FormConfig(service_type=query["service_type"], location_city=query["location_city"],
                            location_area=query["location_area"], urgency=query["urgency"],
                            budget=query["budget"], additional_details=query.get("additional_details"))
        state = resolve_intent(AgentState(config=config))
        state.raw_candidates = local_candidates(db, query, state.intent.resolved_service)
        state.sources = sorted({c.source for c in state.raw_candidates if c.source})
        state = cleanup(state)
        state = rank_and_synthesize(state)
        candidates = [c.model_dump() for c in state.final_candidates]
        results.append({"query_id": query["query_id"], "summary": state.summary,
                        "synthesis_reason": state.synthesis_reason, "candidates": candidates,
                        "sources": state.sources})
        print(f"{index}/{len(queries)} {query['query_id']}: {len(candidates)} candidates")
    jsonl_write(args.out, results)
    db.close()
    print(f"Saved replay output: {args.out}")


if __name__ == "__main__":
    main()
