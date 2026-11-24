"""Prepare a compact, evidence-focused judging dataset from full system traces.

The original trace JSONL is never modified. This output applies field allowlists,
limits review text, and normalizes tool errors before any trace is sent to a judge.
"""
import argparse
import json
import re
from pathlib import Path

from common import jsonl_read, jsonl_write

SEARCH_FIELDS = (
    "name", "title", "full_address", "address", "subtypes", "types", "category",
    "rating", "review_count", "phone_number", "phone", "website", "business_id",
    "whatsapp_number", "email", "google_id", "place_id", "price_level", "open_now",
    "working_hours", "hours", "opening_hours",
)
DETAIL_FIELDS = (
    "name", "title", "full_address", "address", "subtypes", "types", "category",
    "rating", "review_count", "phone_number", "phone", "website", "business_id",
    "whatsapp_number", "email", "google_id", "place_id", "price_level", "open_now",
    "working_hours", "hours", "opening_hours",
)
FINAL_CANDIDATE_FIELDS = (
    "name", "evidence", "phones", "whatsapp_number", "location", "service_tags",
    "price_signal", "source", "business_id", "website", "email", "rating", "reviews_summary",
)
TOOL_INPUT_FIELDS = {
    "business_search": ("query", "limit", "region", "subtypes", "lat", "lng", "zoom"),
    "business_details": ("business_id", "region"),
    "business_reviews": ("business_id", "limit", "sort_by", "query"),
}


def error_text(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)


def classify_error(value, tool):
    text = error_text(value).casefold()
    tool_name = str(tool or "business tool").replace("_", " ")
    status = re.search(r"\b([45]\d\d)\b", text)
    code = status.group(1) if status else None
    if code == "429" or any(term in text for term in ("rate limit", "too many requests", "quota exceeded")):
        return "rate_limit", f"{tool_name} request was rate limited or over quota."
    if code in ("401", "403") or any(term in text for term in ("unauthorized", "forbidden", "authentication", "invalid api key")):
        return "authentication", f"{tool_name} request failed authentication or permission checks."
    if any(term in text for term in ("timeout", "timed out", "readtimeout", "connecttimeout")):
        return "timeout", f"{tool_name} request timed out."
    if code == "404" or "not found" in text:
        return "not_found", f"{tool_name} could not find the requested resource."
    if code and code.startswith("5"):
        return "upstream_server", f"{tool_name} service returned an upstream server error (HTTP {code})."
    if any(term in text for term in ("connectionerror", "connection error", "dns", "sslerror", "network is unreachable")):
        return "network", f"A network error prevented the {tool_name} request."
    if code:
        return "request_error", f"{tool_name} request failed (HTTP {code})."
    return "tool_error", f"{tool_name} returned an error."


def compact_value(value, max_text=500):
    """Bound free text and discard arbitrary nested payloads."""
    if isinstance(value, str):
        value = re.sub(r"\s+", " ", value).strip()
        return value[:max_text]
    if isinstance(value, list):
        return [compact_value(item, max_text) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key)[:80]: compact_value(item, max_text) for key, item in list(value.items())[:30]}
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:max_text]


def pick_fields(record, fields, text_limit=500):
    if not isinstance(record, dict):
        return None
    selected = {}
    for field in fields:
        value = record.get(field)
        if value is not None and value != "" and value != []:
            selected[field] = compact_value(value, text_limit)
    return selected


def compact_reviews(output):
    reviews = output.get("reviews") if isinstance(output, dict) else None
    if not isinstance(reviews, list):
        return None
    compacted = []
    for review in reviews[:3]:
        if not isinstance(review, dict):
            continue
        item = {}
        for field in ("review_text", "text", "rating"):
            value = review.get(field)
            if value is not None and value != "":
                item[field] = compact_value(value, 400)
        if item:
            compacted.append(item)
    return compacted


def compact_tool_output(tool, output):
    if not isinstance(output, dict):
        return compact_value(output, 800)
    if output.get("error"):
        category, message = classify_error(output["error"], tool)
        return {"error_category": category, "error": message}

    if tool == "business_search":
        rows = output.get("data") or output.get("results") or output.get("businesses") or []
        compact_rows = [pick_fields(row, SEARCH_FIELDS) for row in rows[:10] if isinstance(row, dict)] if isinstance(rows, list) else []
        return {"businesses": compact_rows}
    if tool == "business_details":
        return pick_fields(output, DETAIL_FIELDS)
    if tool == "business_reviews":
        return {"reviews": compact_reviews(output) or []}
    return {"status": "tool_response_omitted", "reason": "No approved compact schema for this tool"}


def compact_tool_call(call):
    tool = call.get("tool")
    fields = TOOL_INPUT_FIELDS.get(tool, ())
    inputs = pick_fields(call.get("input") or {}, fields)
    output = compact_tool_output(tool, call.get("output"))
    status = call.get("status", "unknown")
    item = {"tool": tool, "input": inputs or {}, "output": output, "status": status}
    if status == "error" and isinstance(output, dict) and output.get("error_category"):
        item["error_category"] = output["error_category"]
    return item


def compact_response(response):
    if not isinstance(response, dict):
        return None
    candidates = response.get("final_candidates") or []
    compact_candidates = [pick_fields(candidate, FINAL_CANDIDATE_FIELDS, text_limit=500)
                          for candidate in candidates[:10] if isinstance(candidate, dict)]
    return {
        "summary": compact_value(response.get("summary", ""), 1000),
        "candidates": compact_candidates,
        "sources": compact_value(response.get("sources", []), 150),
    }


def compact_trace(row):
    query = row.get("query") or {}
    query_fields = ("service_type", "location_city", "location_area", "urgency", "budget", "additional_details")
    compact_query = pick_fields(query, query_fields, text_limit=300) or {}
    error = row.get("error")
    if error:
        _, error = classify_error(error, "agent run")
    source_calls = row.get("tool_calls", [])
    tool_counts = {}
    for call in source_calls:
        tool = call.get("tool", "unknown")
        tool_counts[tool] = tool_counts.get(tool, 0) + 1
    tool_call_stats = {
        "total": len(source_calls),
        "live_api_calls": sum(call.get("source") == "live" for call in source_calls),
        "cached_responses": sum(call.get("source") in ("cache", "existing_cache") for call in source_calls),
        "errors": sum(call.get("status") == "error" for call in source_calls),
        "by_tool": tool_counts,
    }
    result = {
        "query_id": row.get("query_id"),
        "run_id": row.get("run_id"),
        "system_metadata": row.get("system_metadata"),
        "elapsed_ms": row.get("elapsed_ms"),
        "tool_call_stats": tool_call_stats,
        "query_text": compact_value(row.get("query_text", ""), 500),
        "query": compact_query,
        "tool_calls": [compact_tool_call(call) for call in row.get("tool_calls", [])],
        "response": compact_response(row.get("response")),
        "status": row.get("status", "unknown"),
        "error": error,
        "preparation": {
            "schema": "recommendation_evidence_v1",
            "full_trace_sent": False,
            "review_snippets_max": 3,
            "search_results_max_per_call": 10,
        },
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", nargs="?", default="eval/data/runs/trace_dataset.jsonl")
    parser.add_argument("--out", default="eval/data/runs/trace_dataset_cleaned.jsonl")
    args = parser.parse_args()
    source, output = Path(args.traces), Path(args.out)
    if source.resolve() == output.resolve():
        parser.error("Output must differ from the original trace file; raw traces are preserved")
    rows = jsonl_read(source)
    if not rows:
        parser.error(f"No trace rows found in {source}")

    compacted = [compact_trace(row) for row in rows]
    jsonl_write(output, compacted)
    source_bytes = source.stat().st_size
    output_bytes = output.stat().st_size
    reduction = (1 - output_bytes / source_bytes) * 100 if source_bytes else 0
    print(f"Prepared judge dataset: {output}")
    print(f"Size: {source_bytes:,} -> {output_bytes:,} bytes ({reduction:.1f}% smaller)")
    print("Included: query criteria, compact tool evidence, final candidates and rationale, normalized errors.")
    print("Judge input excludes: non-allowlisted payload fields, review authors, SQL labels, cache metadata, and timings.")
    print("Run metadata, latency, and tool call/cache counts stay in the prepared file for the summary; they are not sent to the judge.")


if __name__ == "__main__":
    main()
