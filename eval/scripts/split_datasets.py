import argparse

from common import DATA, jsonl_read, jsonl_write


def main():
    parser = argparse.ArgumentParser(description="Split reviewed labeled JSONL by its preassigned cell-level split")
    parser.add_argument("labeled_queries", help="Reviewed query JSONL with split=golden or test")
    parser.add_argument("--out-dir", default=str(DATA / "datasets"))
    args = parser.parse_args()
    rows = jsonl_read(args.labeled_queries)
    partitions = {"golden": [], "test": []}
    for row in rows:
        split = row.get("split")
        if split not in partitions:
            raise ValueError(f"{row.get('query_id')}: split must be golden or test")
        partitions[split].append(row)
    if not partitions["golden"] or not partitions["test"]:
        raise ValueError("Both golden and test partitions must contain queries")
    for split, part in partitions.items():
        jsonl_write(f"{args.out_dir}/{split}_v1.jsonl", part)
        print(f"{split}: {len(part)} queries")


if __name__ == "__main__":
    main()
