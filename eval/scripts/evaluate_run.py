import argparse
import json
from pathlib import Path

from common import DATA, connect, jsonl_read


def main():
    parser = argparse.ArgumentParser(description="Score saved run outputs against reviewed labels")
    parser.add_argument("labels", help="Golden/test JSONL")
    parser.add_argument("run", help="replay_generate output JSONL")
    parser.add_argument("--db", default=str(DATA / "corpus.sqlite"))
    parser.add_argument("--report", help="Optional JSON report path")
    args = parser.parse_args()
    labels = {r["query_id"]: r for r in jsonl_read(args.labels)}
    outputs = {r["query_id"]: r for r in jsonl_read(args.run)}
    db = connect(args.db)
    key_by_name = {r["name"].casefold(): r["provider_key"] for r in db.execute("SELECT provider_key,name FROM providers")}
    rows = []
    for qid, label in labels.items():
        output = outputs.get(qid)
        if output is None:
            rows.append({"query_id": qid, "missing_output": True})
            continue
        candidates = output.get("candidates", [])
        ids = [c.get("business_id") or key_by_name.get((c.get("name") or "").casefold()) for c in candidates]
        ids = [x for x in ids if x is not None]
        relevant = set(label.get("expected_provider_ids", [])) | set(label.get("acceptable_provider_ids", []))
        no_result_correct = bool(label.get("no_result_expected")) == (len(candidates) == 0)
        rows.append({"query_id": qid, "top1_correct": bool(ids and ids[0] in relevant),
                     "top3_hit": any(i in relevant for i in ids[:3]),
                     "precision": sum(i in relevant for i in ids) / len(ids) if ids else 0.0,
                     "recall": sum(i in relevant for i in ids) / len(relevant) if relevant else float(not ids),
                     "no_result_correct": no_result_correct,
                     "schema_valid": all(isinstance(c.get("name"), str) and isinstance(c.get("phones", []), list) for c in candidates),
                     "returned_count": len(candidates)})
    n = len(rows)
    valid = [r for r in rows if not r.get("missing_output")]
    report = {"queries_labeled": n, "queries_scored": len(valid),
              "top1_accuracy": sum(r.get("top1_correct", False) for r in valid) / len(valid) if valid else 0,
              "top3_hit_rate": sum(r.get("top3_hit", False) for r in valid) / len(valid) if valid else 0,
              "mean_precision": sum(r.get("precision", 0) for r in valid) / len(valid) if valid else 0,
              "mean_recall": sum(r.get("recall", 0) for r in valid) / len(valid) if valid else 0,
              "no_result_accuracy": sum(r.get("no_result_correct", False) for r in valid) / len(valid) if valid else 0,
              "schema_valid_rate": sum(r.get("schema_valid", False) for r in valid) / len(valid) if valid else 0,
              "per_query": rows}
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(serialized, encoding="utf-8")
    print(serialized)
    db.close()


if __name__ == "__main__":
    main()
