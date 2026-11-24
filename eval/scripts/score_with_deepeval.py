"""Compare full-system outputs with synthetic golden expected outputs."""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", nargs="?", default="eval/data/runs/synthetic_run_v1.jsonl")
    parser.add_argument("--report", default="eval/data/runs/deepeval_report_v1.json")
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()
    try:
        from deepeval import evaluate
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, SingleTurnParams
    except ImportError as exc:
        raise SystemExit("DeepEval is not installed. Run: pip install -r eval/requirements.txt") from exc

    rows = [json.loads(line) for line in Path(args.run).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        parser.error("Run file has no rows")
    if any(not row.get("actual_output") or not row.get("expected_output") for row in rows):
        parser.error("Every run row must include actual_output and expected_output")
    test_cases = [LLMTestCase(input=row["input"], actual_output=row["actual_output"],
                              expected_output=row["expected_output"]) for row in rows]
    correctness = GEval(
        name="LocalServiceAnswerCorrectness",
        evaluation_steps=[
            "Read the input to identify the requested service and location.",
            "Compare the actual output with the expected output and supplied business facts.",
            "Reward returning relevant providers for the requested service and location.",
            "Penalize unsupported business facts, wrong locations or services, and failure to answer the request.",
            "Do not require identical wording; score factual and task correctness.",
        ],
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
        model=args.model,
        async_mode=True,
        threshold=None,
    )
    print(f"Scoring {len(test_cases)} outputs with DeepEval G-Eval; this makes judge-model calls.")
    result = evaluate(test_cases=test_cases, metrics=[correctness])
    per_case = []
    for item in getattr(result, "test_results", []):
        metrics = getattr(item, "metrics_data", [])
        score_metric = next((m for m in metrics if getattr(m, "name", None) == correctness.name), None)
        per_case.append({"name": getattr(item, "name", None),
                         "success": getattr(item, "success", None),
                         "score": getattr(score_metric, "score", None),
                         "reason": getattr(score_metric, "reason", None)})
    scores = [item["score"] for item in per_case if isinstance(item["score"], (int, float))]
    report = {"metric": correctness.name, "cases": len(test_cases),
              "mean_score": sum(scores) / len(scores) if scores else None,
              "scored_cases": len(scores), "results": per_case}
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved DeepEval report: {report_path}")


if __name__ == "__main__":
    main()
