"""Capped, explicit live pull. Never enriches candidates or overwrites a raw pull."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from common import DATA

HOST = "local-business-search.p.rapidapi.com"
URL = f"https://{HOST}/search"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cells", required=True, help="JSON list of {service, city, area} cells")
    parser.add_argument("--max-calls", type=int, default=1, help="Hard cap for this invocation (1..10)")
    parser.add_argument("--start-index", type=int, default=0, help="Zero-based starting cell, for a prior smoke call")
    parser.add_argument("--limit", type=int, default=20, help="Results per API request")
    parser.add_argument("--confirm-live", action="store_true", help="Acknowledge each request may consume API quota")
    args = parser.parse_args()
    if not args.confirm_live:
        parser.error("live requests require --confirm-live")
    if not 1 <= args.max_calls <= 10:
        parser.error("--max-calls must be between 1 and 10")
    load_dotenv()
    key = os.getenv("RAPID_API_KEY")
    if not key:
        parser.error("RAPID_API_KEY is not set")
    cells = json.loads(Path(args.cells).read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = DATA / "snapshots" / stamp
    out_dir.mkdir(parents=True, exist_ok=False)
    if args.start_index < 0 or args.start_index >= len(cells):
        parser.error("--start-index must select a cell")
    selected = cells[args.start_index:args.start_index + args.max_calls]
    manifest = {"created_at": stamp, "requested_max_calls": args.max_calls,
                "start_index": args.start_index, "calls": []}
    for i, cell in enumerate(selected, start=1):
        query = f"{cell['service']} {cell['area']} {cell['city']}"
        params = {"query": query, "limit": args.limit, "region": "ng", "language": "en",
                  "extract_emails_and_contacts": "true"}
        # Request available response fields once for curation; downstream LLM prompts are separately pruned.
        response = requests.get(URL, headers={"x-rapidapi-host": HOST, "x-rapidapi-key": key},
                                params=params, timeout=45)
        response.raise_for_status()
        body = response.json()
        raw_path = out_dir / f"call_{i:02d}.json"
        raw_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["calls"].append({"call": i, "cell": cell, "query": query,
                                  "params": params, "http_status": response.status_code,
                                  "raw_file": raw_path.name})
        (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved call {i}/{args.max_calls}: {cell['service']} / {cell['area']}, {cell['city']}")
    print(f"Snapshot: {out_dir}")


if __name__ == "__main__":
    main()
