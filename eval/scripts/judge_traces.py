"""Judge compact traces in groups, one synchronous LLM request per group."""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from common import jsonl_read

API_URL = "https://api.openai.com/v1/chat/completions"
ISSUE_TYPES = ("fabricated_provider", "wrong_attribute", "unsupported_claim", "ignored_constraint")
RUBRIC_VERSION = "tool_output_grounding_v1"

SYSTEM_PROMPT = """You are a strict evaluator of whether a recommendation agent's final response
is grounded in the business tool outputs it received. Evaluate each case independently.
Use only that case's query, tool calls/results, and response. Do NOT judge whether the
search tools found the best possible providers; retrieval quality is out of scope.

For each case:
1. provider_faithfulness is true only if every business named in the response is present
   in the captured tool outputs (allow reasonable name formatting differences).
2. Count factual provider attributes asserted in the response (such as location, phone,
   email, website, service, rating, hours, price, and review claims). Return
   attributes_checked and how many are directly supported by the captured tool outputs.
   Do not count generic conversational statements.
3. constraint_adherence is true when the response preserves the user's stated service and
   location/constraints, or clearly explains when the captured tool results do not satisfy
   them. It is false if it silently presents a conflicting match as suitable.
4. List each concrete issue using exactly one of these issue_type values:
   fabricated_provider, wrong_attribute, unsupported_claim, ignored_constraint.
   Return at most the two most important issues per case. Include excerpts copied verbatim
   from the captured tool output and response (each no longer than 120 characters) and an
   explanation no longer than 160 characters. Do not invent excerpts.
5. A case passes grounding only when there are no issues, provider_faithfulness is true,
   all checked attributes are supported, and constraint_adherence is true. The program
   computes this pass result from your returned fields; do not return it yourself.

Return ONLY JSON in exactly this shape:
{"results":[{"query_id":"q01","provider_faithfulness":true,
"attributes_checked":2,"attributes_supported":2,"constraint_adherence":true,
"issues":[{"issue_type":"wrong_attribute","tool_output_excerpt":"exact evidence",
"response_excerpt":"exact claim","explanation":"brief reason"}]}]}
If no issues exist, return an empty issues array. Return exactly one result for every
input query_id. Copy each ID exactly; do not infer or generate IDs. Return no additional keys or prose."""


def text_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from text_values(item)


def excerpt_is_exact(excerpt, source):
    return bool(excerpt) and any(excerpt in text for text in text_values(source))


def parse_group_response(content, expected_ids, traces_by_id, allow_partial=False):
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        if not allow_partial:
            raise ValueError(f"Judge response was not valid JSON: {exc}") from exc
        # The API may truncate a long JSON response. Recover complete result objects
        # from its results array; the caller retries only cases not recovered here.
        marker = re.search(r'"results"\s*:\s*\[', content)
        recovered = []
        if marker:
            decoder = json.JSONDecoder()
            index = marker.end()
            while index < len(content):
                while index < len(content) and (content[index].isspace() or content[index] == ","):
                    index += 1
                if index >= len(content) or content[index] == "]":
                    break
                try:
                    value, end = decoder.raw_decode(content, index)
                except json.JSONDecodeError:
                    break
                if isinstance(value, dict):
                    recovered.append(value)
                index = end
        if not recovered:
            return {}
        payload = {"results": recovered}
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise ValueError("Judge response must contain a results array")

    parsed = {}
    expected_id_set = set(expected_ids)
    for item in results:
        if not isinstance(item, dict) or not item.get("query_id"):
            raise ValueError("Each judge result must include query_id")
        query_id = str(item["query_id"])
        if query_id not in expected_id_set:
            # Discard stray IDs and retry only the expected cases omitted by the judge.
            continue
        if query_id in parsed:
            # Keep the first result; a repeated ID cannot satisfy a missing case.
            continue
        for field in ("provider_faithfulness", "constraint_adherence"):
            if not isinstance(item.get(field), bool):
                raise ValueError(f"{query_id}: {field} must be a boolean")
        checked, supported = item.get("attributes_checked"), item.get("attributes_supported")
        if isinstance(checked, bool) or not isinstance(checked, int) or checked < 0:
            raise ValueError(f"{query_id}: attributes_checked must be a nonnegative integer")
        if isinstance(supported, bool) or not isinstance(supported, int) or not 0 <= supported <= checked:
            raise ValueError(f"{query_id}: attributes_supported must be an integer from 0 to attributes_checked")
        issues = item.get("issues")
        if not isinstance(issues, list):
            raise ValueError(f"{query_id}: issues must be an array")
        clean_issues = []
        for issue in issues:
            if not isinstance(issue, dict) or issue.get("issue_type") not in ISSUE_TYPES:
                raise ValueError(f"{query_id}: issue_type must be one of {', '.join(ISSUE_TYPES)}")
            clean_issues.append({
                "issue_type": issue["issue_type"],
                "tool_output_excerpt": str(issue.get("tool_output_excerpt", ""))[:120],
                "response_excerpt": str(issue.get("response_excerpt", ""))[:120],
                "explanation": str(issue.get("explanation", ""))[:160],
            })
        issue_types = {issue["issue_type"] for issue in clean_issues}
        source_row = traces_by_id[query_id]
        for issue in clean_issues:
            issue["excerpt_verification"] = {
                "tool_output_exact": excerpt_is_exact(
                    issue["tool_output_excerpt"],
                    [call.get("output") for call in source_row.get("tool_calls", [])],
                ),
                "response_exact": excerpt_is_exact(issue["response_excerpt"], source_row.get("response")),
            }
        consistency_warnings = []
        if item["provider_faithfulness"] is False and "fabricated_provider" not in issue_types:
            consistency_warnings.append("provider_faithfulness=false without a fabricated_provider issue")
        if item["provider_faithfulness"] is True and "fabricated_provider" in issue_types:
            consistency_warnings.append("fabricated_provider issue conflicts with provider_faithfulness=true")
        if supported < checked and not ({"wrong_attribute", "unsupported_claim"} & issue_types):
            consistency_warnings.append("unsupported attributes counted without a wrong_attribute or unsupported_claim issue")
        if item["constraint_adherence"] is False and "ignored_constraint" not in issue_types:
            consistency_warnings.append("constraint_adherence=false without an ignored_constraint issue")
        if item["constraint_adherence"] is True and "ignored_constraint" in issue_types:
            consistency_warnings.append("ignored_constraint issue conflicts with constraint_adherence=true")
        # Resolve conflicts conservatively: explicit issue records make the associated
        # boolean metric fail, while preserving the judge's raw counts and warnings.
        provider_faithful = item["provider_faithfulness"] and "fabricated_provider" not in issue_types
        constraint_adherent = item["constraint_adherence"] and "ignored_constraint" not in issue_types
        attr_accuracy = supported / checked if checked else None
        passes = (
            not clean_issues
            and provider_faithful
            and supported == checked
            and constraint_adherent
        )
        parsed[query_id] = {
            "provider_faithfulness": provider_faithful,
            "attributes_checked": checked,
            "attributes_supported": supported,
            "attribute_accuracy": attr_accuracy,
            "has_unsupported_claim": "unsupported_claim" in issue_types,
            "constraint_adherence": constraint_adherent,
            "grounding_pass": passes,
            "issues": clean_issues,
            "consistency_warnings": consistency_warnings,
        }

    if set(parsed) != expected_id_set:
        missing = sorted(expected_id_set - set(parsed))
        if not allow_partial:
            raise ValueError(f"Judge omitted query_id(s): {missing}")
    return parsed


def request_judge_group(group, headers, model):
    request_payload = {"cases": [{
        "query_id": str(row["query_id"]),
        "query_text": row.get("query_text"),
        "query": row.get("query"),
        "tool_calls": row.get("tool_calls", []),
        "response": row.get("response"),
        "run_status": row.get("status"),
        "run_error": row.get("error"),
    } for row in group]}
    response = requests.post(
        API_URL,
        headers=headers,
        json={
            "model": model,
            "temperature": 0,
            "max_tokens": max(3000, 1000 * len(group)),
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(request_payload, ensure_ascii=False, separators=(",", ":"))},
            ],
        },
        timeout=(20, 240),
    )
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices", [])
    content = choices[0].get("message", {}).get("content") if choices else None
    if not content:
        raise ValueError("Judge returned an empty response")
    return content, body.get("usage") or {}


def atomic_write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(path)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", nargs="?", default="eval/data/runs/trace_dataset_cleaned.jsonl")
    parser.add_argument("--out", default="eval/data/runs/judged_dataset_grouped.jsonl")
    parser.add_argument("--model", help="Defaults to core/config.yaml base_model")
    parser.add_argument("--batch-size", type=int, choices=(5, 10), default=5,
                        help="Trace records per synchronous LLM request")
    parser.add_argument("--resume", action="store_true", help="Skip query IDs already present in --out")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        parser.error("OPENAI_API_KEY is missing from the environment/.env")
    if not args.model:
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root))
        from core.config import Config
        args.model = Config.BASE_MODEL

    source_path, out_path = Path(args.traces), Path(args.out)
    if source_path.resolve() == out_path.resolve():
        parser.error("Output must differ from input; preserve the prepared judging dataset")
    rows = jsonl_read(source_path)
    if not rows:
        parser.error(f"No trace rows found in {source_path}")
    if any((row.get("preparation") or {}).get("schema") != "recommendation_evidence_v1" for row in rows):
        parser.error("Input is not the compact judging dataset. Run eval/scripts/clean_tool_errors.py first.")
    ids = [str(row.get("query_id", "")) for row in rows]
    if any(not query_id for query_id in ids) or len(set(ids)) != len(ids):
        parser.error("Every trace needs a unique query_id")
    if out_path.exists() and not args.resume:
        parser.error(f"Output already exists: {out_path}; choose another --out or pass --resume")

    judged_rows = {}
    if out_path.exists():
        for row in jsonl_read(out_path):
            if row.get("query_id"):
                judged_rows[str(row["query_id"])] = row
    for row in rows:
        if row.get("response") is None:
            skipped = dict(row)
            skipped["judgment"] = None
            skipped["judge_status"] = "not_evaluated_no_response"
            judged_rows.setdefault(str(row["query_id"]), skipped)
    pending = [row for row in rows
               if row.get("response") is not None and str(row["query_id"]) not in judged_rows]
    groups = [pending[i:i + args.batch_size] for i in range(0, len(pending), args.batch_size)]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    print(f"Scoring {len(pending)} response(s) in {len(groups)} synchronous LLM request(s) using {args.model}.")

    for group in groups:
        expected_ids = [str(row["query_id"]) for row in group]
        group_id = hashlib.sha256("|".join(expected_ids).encode("utf-8")).hexdigest()[:12]
        traces_by_id = {str(row["query_id"]): row for row in group}
        unresolved = list(group)
        results = {}
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for attempt in range(3):
            if not unresolved:
                break
            content, call_usage = request_judge_group(unresolved, headers, args.model)
            for token_name in usage:
                usage[token_name] += int(call_usage.get(token_name, 0) or 0)
            expected = [str(row["query_id"]) for row in unresolved]
            results.update(parse_group_response(content, expected, traces_by_id, allow_partial=True))
            # Persist every valid result immediately, even if this response omitted
            # another case. An interruption or retry then cannot discard scored cases.
            judged_at = datetime.now(timezone.utc).isoformat()
            for row in group:
                query_id = str(row["query_id"])
                if query_id not in results:
                    continue
                updated = dict(row)
                judgment = dict(results[query_id])
                judgment.update({"judge_model": args.model, "rubric_version": RUBRIC_VERSION})
                updated["judgment"] = judgment
                updated["judge_status"] = "judged"
                updated["judge_group_id"] = group_id
                updated["judge_call"] = {
                    "model": args.model,
                    "rubric_version": RUBRIC_VERSION,
                    "group_id": group_id,
                    "evaluated_at": judged_at,
                    "usage": dict(usage),
                }
                judged_rows[query_id] = updated
            partial_rows = [judged_rows[str(row["query_id"])] for row in rows
                            if str(row["query_id"]) in judged_rows]
            atomic_write_jsonl(out_path, partial_rows)
            unresolved = [row for row in unresolved if str(row["query_id"]) not in results]
            if unresolved:
                missing_ids = ", ".join(str(row["query_id"]) for row in unresolved)
                print(f"Judge omitted {missing_ids}; retrying only those case(s) (attempt {attempt + 2}/3).")
        if unresolved:
            missing_ids = ", ".join(str(row["query_id"]) for row in unresolved)
            raise ValueError(f"Judge did not return results for {missing_ids} after 3 attempts; prior groups remain checkpointed.")
        judged_at = datetime.now(timezone.utc).isoformat()

        for row in group:
            updated = dict(row)
            judgment = dict(results[str(row["query_id"])])
            judgment.update({"judge_model": args.model, "rubric_version": RUBRIC_VERSION})
            updated["judgment"] = judgment
            updated["judge_status"] = "judged"
            updated["judge_group_id"] = group_id
            updated["judge_call"] = {
                "model": args.model,
                "rubric_version": RUBRIC_VERSION,
                "group_id": group_id,
                "evaluated_at": judged_at,
                "usage": usage,
            }
            judged_rows[str(row["query_id"])] = updated

        ordered = [judged_rows[str(row["query_id"])] for row in rows
                   if str(row["query_id"]) in judged_rows]
        atomic_write_jsonl(out_path, ordered)
        print(f"Completed group {group_id}: {', '.join(expected_ids)}")

    ordered = [judged_rows[str(row["query_id"])] for row in rows
               if str(row["query_id"]) in judged_rows]
    atomic_write_jsonl(out_path, ordered)
    evaluated = sum(row.get("judge_status") == "judged" for row in ordered)
    print(f"Judged dataset: {out_path} ({evaluated}/{len(rows)} responses evaluated)")


if __name__ == "__main__":
    main()
