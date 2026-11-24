"""Create the machine-readable grounding evaluation summary from judged traces."""
import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, jsonl_read

ISSUE_TYPES = ("fabricated_provider", "wrong_attribute", "unsupported_claim", "ignored_constraint")
METHOD = "tool-output grounding (response vs tool responses)"


def git_value(*args):
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def normalize_remote(remote):
    if not remote:
        return ""
    if remote.startswith("git@github.com:"):
        remote = "https://github.com/" + remote.split(":", 1)[1]
    elif remote.startswith("ssh://git@github.com/"):
        remote = "https://github.com/" + remote.removeprefix("ssh://git@github.com/")
    if remote.endswith(".git"):
        remote = remote[:-4]
    return remote if remote.startswith("https://github.com/") else ""


def blob_exists(commit, relative_path):
    if not commit or not relative_path:
        return False
    try:
        subprocess.run(["git", "cat-file", "-e", f"{commit}:{relative_path}"], cwd=ROOT,
                       check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def make_links(remote, commit, dataset_path, results_path, dirty):
    links = {"repo": remote, "eval_script": "", "dataset": "", "results": "", "rubric": ""}
    if not remote or not commit or dirty:
        return links
    paths = {
        "eval_script": "eval/scripts/judge_traces.py",
        "dataset": dataset_path,
        "results": results_path,
        "rubric": "eval/rubric.md",
    }
    for key, relative_path in paths.items():
        # A permalink is only emitted when that exact file exists in the recorded commit.
        if blob_exists(commit, relative_path):
            links[key] = f"{remote}/blob/{commit}/{relative_path}"
    return links


def run_date_from_rows(rows):
    dates = []
    for row in rows:
        run_id = row.get("run_id")
        if run_id:
            try:
                dates.append(datetime.strptime(run_id, "%Y%m%dT%H%M%SZ").date().isoformat())
            except ValueError:
                pass
    return min(dates) if dates else datetime.now(timezone.utc).date().isoformat()


def query_label(row):
    return row.get("query_text") or json.dumps(row.get("query", {}), ensure_ascii=False)


def build_summary(rows, dataset_path, results_path, repo_override=None):
    if not rows:
        raise ValueError("No judged trace records found")

    evaluated = [row for row in rows if row.get("judge_status") == "judged" and isinstance(row.get("judgment"), dict)]
    run_failures = [row for row in rows if row.get("status") != "success" or row.get("response") is None]
    judgments = [row["judgment"] for row in evaluated]

    passed = sum(bool(item.get("grounding_pass")) for item in judgments)
    provider_faithful = sum(item.get("provider_faithfulness") is True for item in judgments)
    constraint_adherent = sum(item.get("constraint_adherence") is True for item in judgments)
    unsupported_cases = sum(bool(item.get("has_unsupported_claim")) for item in judgments)
    checked_attributes = sum(int(item.get("attributes_checked", 0)) for item in judgments)
    supported_attributes = sum(int(item.get("attributes_supported", 0)) for item in judgments)

    issue_counts = Counter({issue_type: 0 for issue_type in ISSUE_TYPES})
    failures = []
    for row in evaluated:
        judgment = row["judgment"]
        for issue in judgment.get("issues", []):
            issue_type = issue.get("issue_type")
            if issue_type not in ISSUE_TYPES:
                continue
            issue_counts[issue_type] += 1
            failures.append({
                "query": query_label(row),
                "tool_output_excerpt": issue.get("tool_output_excerpt", ""),
                "response_excerpt": issue.get("response_excerpt", ""),
                "issue_type": issue_type,
                "explanation": issue.get("explanation", ""),
                "query_id": row.get("query_id"),
                "excerpt_verification": issue.get("excerpt_verification", {}),
            })

    latency_values = [row["elapsed_ms"] / 1000 for row in rows
                      if isinstance(row.get("elapsed_ms"), (int, float))]
    tool_stats = [row.get("tool_call_stats") or {} for row in rows]
    tool_call_total = sum(stats.get("total", 0) for stats in tool_stats)
    live_api_calls = sum(stats.get("live_api_calls", 0) for stats in tool_stats)
    cached_tool_responses = sum(stats.get("cached_responses", 0) for stats in tool_stats)
    tool_errors = sum(stats.get("errors", 0) for stats in tool_stats)
    tool_counts = Counter()
    for stats in tool_stats:
        tool_counts.update(stats.get("by_tool", {}))

    judge_calls = {}
    for row in evaluated:
        call = row.get("judge_call") or {}
        group_id = call.get("group_id")
        if group_id and group_id not in judge_calls:
            judge_calls[group_id] = call
    judge_input_tokens = sum((call.get("usage") or {}).get("prompt_tokens", 0) for call in judge_calls.values())
    judge_output_tokens = sum((call.get("usage") or {}).get("completion_tokens", 0) for call in judge_calls.values())
    judge_models = sorted({(row.get("judgment") or {}).get("judge_model") for row in evaluated
                           if (row.get("judgment") or {}).get("judge_model")})
    rubric_versions = sorted({(row.get("judgment") or {}).get("rubric_version") for row in evaluated
                              if (row.get("judgment") or {}).get("rubric_version")})

    metadata_rows = [row.get("system_metadata") or {} for row in rows if row.get("system_metadata")]
    commit_shas = sorted({meta.get("commit_sha") for meta in metadata_rows if meta.get("commit_sha")})
    commit_sha = commit_shas[0] if len(commit_shas) == 1 else ("multiple" if commit_shas else "")
    agent_model_configs = {
        tuple(sorted(meta.get("agent_models", {}).items()))
        for meta in metadata_rows if meta.get("agent_models")
    }
    if not agent_model_configs:
        agent_model = "unknown (not recorded in trace)"
    elif len(agent_model_configs) == 1:
        agent_model = ", ".join(f"{key}={value}" for key, value in next(iter(agent_model_configs)))
    else:
        agent_model = "multiple: " + " | ".join(
            ", ".join(f"{key}={value}" for key, value in config) for config in sorted(agent_model_configs)
        )
    dirty = any(meta.get("working_tree_dirty") is True for meta in metadata_rows)

    repo = normalize_remote(repo_override or git_value("config", "--get", "remote.origin.url"))
    recorded_dataset_paths = {meta.get("query_file") for meta in metadata_rows if meta.get("query_file")}
    if len(recorded_dataset_paths) == 1:
        dataset_path = next(iter(recorded_dataset_paths))
    elif len(recorded_dataset_paths) > 1:
        dataset_path = ""
    links = make_links(repo, commit_sha if commit_sha != "multiple" else "", dataset_path, results_path, dirty)

    metrics = {
        "provider_faithfulness": provider_faithful / len(evaluated) if evaluated else None,
        "attribute_accuracy": supported_attributes / checked_attributes if checked_attributes else None,
        "unsupported_claim_rate": unsupported_cases / len(evaluated) if evaluated else None,
        "constraint_adherence": constraint_adherent / len(evaluated) if evaluated else None,
        "avg_latency_s": sum(latency_values) / len(latency_values) if latency_values else None,
        "business_tool_calls": tool_call_total,
        "live_business_api_calls": live_api_calls,
        "cached_business_tool_responses": cached_tool_responses,
        "business_tool_error_rate": tool_errors / tool_call_total if tool_call_total else None,
        "judge_llm_calls": len(judge_calls),
        "judge_input_tokens": judge_input_tokens,
        "judge_output_tokens": judge_output_tokens,
    }

    limitations = [
        "Measures response faithfulness to captured tool outputs, not whether retrieval found the best providers.",
        "LLM judge decisions may be imperfect; inspect the cited trace excerpts for important failures.",
        "The judge saw an allowlisted, compacted evidence view; omitted API fields were not evaluated.",
        "Dollar cost is omitted; the summary records judge token usage but does not apply model pricing or include agent token usage.",
    ]
    if len(evaluated) < 25:
        limitations.append(f"Small sample: only {len(evaluated)} responses were judged.")
    if run_failures:
        limitations.append(f"{len(run_failures)} of {len(rows)} agent runs had no successful final response and were excluded from grounding rates.")
    if not metadata_rows:
        limitations.append("The trace did not record run-time commit or agent model metadata; these cannot be reconstructed reliably.")
    elif dirty:
        limitations.append("The agent code working tree was dirty during at least one recorded run; commit_sha alone does not identify those uncommitted changes.")
    elif commit_sha == "multiple":
        limitations.append("The traces span multiple source commits; each case is recorded, but the summary cannot point to one evaluated version.")
    elif not commit_sha:
        limitations.append("No run-time commit SHA was captured, so source permalinks could not be pinned to the evaluated code.")
    if any(row.get("run_id") for row in rows) and len({row.get("run_id") for row in rows if row.get("run_id")}) > 1:
        limitations.append("The judged dataset contains records from multiple agent run sessions.")
    if checked_attributes == 0:
        limitations.append("No factual attributes were counted by the judge, so attribute_accuracy is unavailable.")
    unverified_excerpts = sum(
        not (issue.get("excerpt_verification", {}).get("tool_output_exact")
             and issue.get("excerpt_verification", {}).get("response_exact"))
        for row in evaluated for issue in (row.get("judgment") or {}).get("issues", [])
    )
    if unverified_excerpts:
        limitations.append(f"{unverified_excerpts} judge-generated failure excerpt(s) did not exactly match the compact evidence text; verify them manually.")
    consistency_warnings = sum(
        len((row.get("judgment") or {}).get("consistency_warnings", [])) for row in evaluated
    )
    if consistency_warnings:
        limitations.append(f"The judge returned {consistency_warnings} internally inconsistent field/issue combination(s); affected booleans were resolved conservatively and warnings are retained in the judged dataset.")

    judge_description = "; ".join(judge_models) if judge_models else "unknown (not recorded)"
    if rubric_versions:
        judge_description += "; rubric " + ", ".join(rubric_versions)
    summary = {
        "project": "Local Services Finder",
        "run_date": run_date_from_rows(rows),
        "commit_sha": commit_sha or "unknown",
        "agent_model": agent_model,
        "method": METHOD,
        "judge": judge_description,
        "cases_evaluated": len(evaluated),
        "runs_attempted": len(rows),
        "grounding_pass_rate": passed / len(evaluated) if evaluated else None,
        "metrics": metrics,
        "by_issue_type": dict(issue_counts),
        "business_tool_calls_by_tool": dict(tool_counts),
        "failures": failures,
        "limitations": limitations,
        "links": links,
        "run_failures": [{"query_id": row.get("query_id"), "query": query_label(row), "error": row.get("error")}
                         for row in run_failures],
        "metric_definitions": {
            "grounding_pass_rate": "Share of judged responses with no recorded issues, all named providers found in tool outputs, all checked attributes supported, and constraints respected.",
            "provider_faithfulness": "Share of judged responses whose every named provider appears in tool outputs.",
            "attribute_accuracy": "Supported factual attributes divided by all factual attributes checked across judged responses.",
            "unsupported_claim_rate": "Share of judged responses containing at least one unsupported-claim issue.",
            "constraint_adherence": "Share of judged responses that preserve or clearly address the query's service/location/constraints.",
            "by_issue_type": "Counts issue occurrences; a single response may contribute more than one issue.",
            "avg_latency_s": "Mean captured agent wall-clock duration per run, including tool and model calls.",
            "business_tool_calls": "Total captured business search, detail, and review tool invocations.",
            "live_business_api_calls": "Tool calls that went to the configured live business API.",
            "cached_business_tool_responses": "Tool calls served by the persistent or pre-existing response cache.",
            "business_tool_error_rate": "Captured tool calls with error status divided by all captured tool calls.",
            "judge_llm_calls": "Number of synchronous grouped judge requests, deduplicated by group_id.",
            "judge_input_tokens/judge_output_tokens": "Token usage reported by the judge API; does not include agent model token usage.",
        },
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", nargs="?", default="eval/data/runs/judged_dataset_grouped.jsonl")
    parser.add_argument("--out", default="eval/data/runs/eval_summary.json")
    parser.add_argument("--dataset-path", default="eval/data/queries_draft.jsonl",
                        help="Repository-relative query dataset path used to build a permalink")
    parser.add_argument("--repo-url", help="Override GitHub repository URL used for pinned links")
    args = parser.parse_args()

    rows = jsonl_read(args.traces)
    if not rows:
        parser.error(f"No judged trace rows found in {args.traces}")
    summary = build_summary(rows, args.dataset_path, args.out, args.repo_url)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Evaluation summary: {output}")
    print(json.dumps({
        "cases_evaluated": summary["cases_evaluated"],
        "grounding_pass_rate": summary["grounding_pass_rate"],
        "metrics": summary["metrics"],
        "failures": len(summary["failures"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
