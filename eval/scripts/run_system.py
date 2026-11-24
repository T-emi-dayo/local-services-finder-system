"""Run existing evaluation queries through the live LSF agent and record traces.

This command makes the system's configured business API and LLM calls. It records
tool inputs/outputs as they happen, checkpoints completed query rows, and reuses
successful exact-request tool responses from a persistent cache on reruns.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from common import DATA, jsonl_read


def json_safe(value):
    """Convert API/Pydantic values to JSON-safe data without losing structure."""
    if hasattr(value, "model_dump"):
        return json_safe(value.model_dump())
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return str(value)


def request_key(tool, args):
    raw = json.dumps([tool, args], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TraceRecorder:
    def __init__(self, events_path, cache_path, legacy_cache_path=None):
        self.events_path = Path(events_path)
        self.cache_path = Path(cache_path)
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.events = []
        self.current_query = None
        self.cache = self._read_cache(self.cache_path)
        # Reuse the existing detail/review cache produced by the previous runner.
        self.legacy_cache = self._read_cache(Path(legacy_cache_path)) if legacy_cache_path else {}

    @staticmethod
    def _read_cache(path):
        if not path or not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_cache(self):
        tmp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(self.cache_path)

    def call(self, name, args, invoke):
        started = time.perf_counter()
        key = request_key(name, args)
        legacy_name = {"business_details": "details", "business_reviews": "reviews"}.get(name)
        legacy_key = json.dumps([legacy_name, args], sort_keys=True, default=str) if legacy_name else None
        source = "live"
        error = None
        try:
            if key in self.cache:
                value, source = self.cache[key], "cache"
            elif legacy_key and legacy_key in self.legacy_cache:
                value, source = self.legacy_cache[legacy_key], "existing_cache"
                self.cache[key] = value
                self._save_cache()
            else:
                value = invoke()
                safe = json_safe(value)
                # Cache only successful tool responses; don't persist errors as facts.
                if not (isinstance(safe, dict) and safe.get("error")):
                    self.cache[key] = safe
                    self._save_cache()
                value = safe
        except Exception as exc:
            value = None
            error = f"{type(exc).__name__}: {exc}"
        event = {
            "query_id": self.current_query,
            "tool": name,
            "input": json_safe(args),
            "output": json_safe(value),
            "status": "error" if error or (isinstance(value, dict) and value.get("error")) else "success",
            "error": error,
            "source": source,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        self.events.append(event)
        # Flush each tool event so an interrupted run still has its evidence.
        with self.events_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        if error:
            raise RuntimeError(error)
        return value


class TracedTool:
    def __init__(self, wrapped, name, recorder):
        self.wrapped, self.name, self.recorder = wrapped, name, recorder

    def invoke(self, args, *rest, **kwargs):
        return self.recorder.call(self.name, args, lambda: self.wrapped.invoke(args, *rest, **kwargs))

    def __getattr__(self, name):
        return getattr(self.wrapped, name)


class TracedFunction:
    def __init__(self, wrapped, name, recorder):
        self.wrapped, self.name, self.recorder = wrapped, name, recorder

    def __call__(self, **args):
        return self.recorder.call(self.name, args, lambda: self.wrapped(**args))


def load_queries(path):
    rows = jsonl_read(path)
    if not rows:
        raise ValueError(f"No query records found in {path}")
    required = ("query_id", "service_type", "location_city", "location_area", "urgency", "budget")
    for row in rows:
        missing = [field for field in required if not row.get(field)]
        if missing:
            raise ValueError(f"{row.get('query_id', '<unknown>')} missing fields: {', '.join(missing)}")
    return rows


def git_metadata(repo_root):
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root, check=True,
            capture_output=True, text=True,
        ).stdout.splitlines()
        return {"commit_sha": commit, "working_tree_dirty": bool(status), "working_tree_changes": status}
    except (OSError, subprocess.CalledProcessError):
        return {"commit_sha": None, "working_tree_dirty": None, "working_tree_changes": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries", nargs="?", default="eval/data/queries_draft.jsonl")
    parser.add_argument("--out", default=str(DATA / "runs/trace_dataset.jsonl"))
    parser.add_argument("--events", default=str(DATA / "runs/tool_events.jsonl"))
    parser.add_argument("--cache", default=str(DATA / "runs/tool_response_cache.json"))
    parser.add_argument("--legacy-cache", default=str(DATA / "enrichment_cache.json"))
    parser.add_argument("--limit", type=int, help="Run only the first N queries")
    parser.add_argument("--resume", action="store_true", help="Skip query IDs already in --out")
    parser.add_argument("--confirm-live", action="store_true", help="Acknowledge this runs the configured LLM and business APIs")
    args = parser.parse_args()
    if not args.confirm_live:
        parser.error("live system calls require --confirm-live")

    queries = load_queries(args.queries)
    if args.limit:
        queries = queries[:args.limit]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.resume:
        parser.error(f"Output already exists: {out}; choose another --out or pass --resume")
    completed = {row.get("query_id") for row in jsonl_read(out)} if out.exists() else set()
    queries = [row for row in queries if row["query_id"] not in completed]

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    from src.agent.graph import LSFAgent
    from src.agent.nodes import ToolOrchestrationNode as tools_node
    from src.models.FormConfig import FormConfig
    from core.config import Config

    recorder = TraceRecorder(args.events, args.cache, args.legacy_cache)
    tools_node.search_local_businesses = TracedFunction(
        tools_node.search_local_businesses, "business_search", recorder
    )
    tools_node.get_business_details = TracedTool(
        tools_node.get_business_details, "business_details", recorder
    )
    tools_node.get_business_reviews = TracedTool(
        tools_node.get_business_reviews, "business_reviews", recorder
    )
    agent = LSFAgent()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        query_file = Path(args.queries).resolve().relative_to(repo_root).as_posix()
    except ValueError:
        query_file = None
    run_metadata = {
        **git_metadata(repo_root),
        "query_file": query_file,
        "agent_models": {
            "base_model": Config.BASE_MODEL,
            "synthesis_model": Config.SYNTHESIS_MODEL,
        },
    }

    for index, query in enumerate(queries, 1):
        recorder.current_query = query["query_id"]
        event_start = len(recorder.events)
        started = time.perf_counter()
        try:
            config_fields = {key: query[key] for key in (
                "service_type", "location_city", "location_area", "urgency", "budget", "additional_details"
            ) if key in query}
            response = agent.run(FormConfig(**config_fields))
            record = {
                "run_id": run_id,
                "system_metadata": run_metadata,
                "query_id": query["query_id"],
                "query_text": query.get("query_text", ""),
                "query": config_fields,
                "tool_calls": recorder.events[event_start:],
                "response": json_safe(response),
                "status": "success",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "judgment": {
                    "data_sufficiency": None,
                    "recommendation_relevance": None,
                    "ranking_quality": None,
                    "response_supported_by_tool_data": None,
                    "notes": None,
                },
            }
        except Exception as exc:
            record = {
                "run_id": run_id,
                "system_metadata": run_metadata,
                "query_id": query["query_id"],
                "query_text": query.get("query_text", ""),
                "query": {key: query.get(key) for key in (
                    "service_type", "location_city", "location_area", "urgency", "budget", "additional_details"
                )},
                "tool_calls": recorder.events[event_start:],
                "response": None,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "judgment": None,
            }
        with out.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        print(f"{index}/{len(queries)} {query['query_id']}: {record['status']}, {len(record['tool_calls'])} tool calls")
    print(f"Trace dataset: {out}")
    print(f"Tool event log: {args.events}")
    print(f"Persistent response cache: {args.cache}")


if __name__ == "__main__":
    main()
