import argparse
import csv

from common import DATA, jsonl_read, jsonl_write


def parse_ids(value):
    return [x.strip() for x in (value or "").split(";") if x.strip()]


def main():
    parser = argparse.ArgumentParser(description="Apply human decisions from label_review.csv to the query drafts")
    parser.add_argument("--queries", default=str(DATA / "queries_draft.jsonl"))
    parser.add_argument("--sheet", default=str(DATA / "label_review.csv"))
    parser.add_argument("--out", default=str(DATA / "queries_reviewed.jsonl"))
    args = parser.parse_args()
    rows = {r["query_id"]: r for r in jsonl_read(args.queries)}
    with open(args.sheet, newline="", encoding="utf-8-sig") as stream:
        reviewed = {r["query_id"]: r for r in csv.DictReader(stream)}
    if rows.keys() != reviewed.keys():
        raise ValueError("Review sheet query IDs do not match the query draft")
    for qid, row in rows.items():
        decision = reviewed[qid]
        row["expected_provider_ids"] = parse_ids(decision["expected_provider_ids"])
        row["acceptable_provider_ids"] = parse_ids(decision["acceptable_provider_ids"])
        row["no_result_expected"] = decision["no_result_expected"].strip().lower() == "true"
        row["review_status"] = decision["review_status"].strip().lower()
        row["review_notes"] = decision.get("review_notes", "")
    jsonl_write(args.out, list(rows.values()))
    print(f"Applied review decisions: {args.out}")


if __name__ == "__main__":
    main()
