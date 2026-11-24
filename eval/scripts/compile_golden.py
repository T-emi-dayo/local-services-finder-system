import argparse
import json
from pathlib import Path

from common import DATA, connect, jsonl_read, jsonl_write


def main():
    parser = argparse.ArgumentParser(description="Validate human-reviewed query labels against the frozen corpus")
    parser.add_argument("labeled_queries", help="JSONL authored independently, then human-labeled")
    parser.add_argument("--db", default=str(DATA / "corpus.sqlite"))
    parser.add_argument("--out", default=str(DATA / "golden_v1.jsonl"))
    args = parser.parse_args()
    db = connect(args.db)
    known = {row[0] for row in db.execute("SELECT provider_key FROM providers")}
    rows = jsonl_read(args.labeled_queries)
    required = {"query_id", "service_type", "location_city", "location_area", "urgency", "budget",
                "expected_provider_ids", "acceptable_provider_ids", "no_result_expected", "review_status"}
    seen = set()
    for row in rows:
        missing = required - row.keys()
        if missing:
            raise ValueError(f"{row.get('query_id', '<unknown>')}: missing {sorted(missing)}")
        if row["query_id"] in seen:
            raise ValueError(f"Duplicate query_id: {row['query_id']}")
        if row["review_status"] != "human_reviewed":
            raise ValueError(f"{row['query_id']}: set review_status=human_reviewed only after checking its labels")
        seen.add(row["query_id"])
        labels = set(row["expected_provider_ids"]) | set(row["acceptable_provider_ids"])
        unknown = labels - known
        if unknown:
            raise ValueError(f"{row['query_id']}: provider IDs absent from corpus: {sorted(unknown)}")
        if row["no_result_expected"] and labels:
            raise ValueError(f"{row['query_id']}: no-result label conflicts with provider IDs")
        if not row["no_result_expected"] and not row["expected_provider_ids"]:
            raise ValueError(f"{row['query_id']}: add expected provider IDs or mark no-result")
    jsonl_write(args.out, rows)
    print(f"Validated {len(rows)} labels -> {args.out}")
    db.close()


if __name__ == "__main__":
    main()
