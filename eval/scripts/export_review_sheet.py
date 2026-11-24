import argparse
import csv

from common import DATA, connect, jsonl_read


def main():
    parser = argparse.ArgumentParser(description="Export candidate golden labels for human review (no contact details)")
    parser.add_argument("queries", nargs="?", default=str(DATA / "queries_draft.jsonl"))
    parser.add_argument("--db", default=str(DATA / "corpus.sqlite"))
    parser.add_argument("--out", default=str(DATA / "label_review.csv"))
    args = parser.parse_args()
    db = connect(args.db)
    names = {r["provider_key"]: f"{r['name']} [{r['category']}] ({r['area']}, {r['city']})"
             for r in db.execute("SELECT provider_key,name,category,area,city FROM providers")}
    with open(args.out, "w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["query_id", "split", "query_text", "candidate_ids",
            "candidate_names", "expected_provider_ids", "acceptable_provider_ids", "no_result_expected",
            "review_status", "review_notes"])
        writer.writeheader()
        for row in jsonl_read(args.queries):
            ids = row.get("expected_provider_ids", [])
            writer.writerow({"query_id": row["query_id"], "split": row.get("split", ""),
                "query_text": row.get("query_text", ""), "candidate_ids": ";".join(ids),
                "candidate_names": " | ".join(names.get(i, i) for i in ids),
                "expected_provider_ids": ";".join(ids),
                "acceptable_provider_ids": ";".join(row.get("acceptable_provider_ids", [])),
                "no_result_expected": str(row.get("no_result_expected", False)).lower(),
                "review_status": "pending", "review_notes": row.get("review_notes", "")})
    db.close()
    print(f"Review sheet: {args.out}")


if __name__ == "__main__":
    main()
