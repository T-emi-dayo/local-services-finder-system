import argparse
import json
from pathlib import Path

from common import DATA, connect, create_db, extract_records, to_provider


def main():
    parser = argparse.ArgumentParser(description="Import saved API JSON into a local SQLite/FTS corpus")
    parser.add_argument("snapshot", help="Snapshot directory containing manifest.json")
    parser.add_argument("--db", default=str(DATA / "corpus.sqlite"))
    args = parser.parse_args()
    snapshot = Path(args.snapshot)
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    db = create_db(connect(args.db))
    inserted = skipped = 0
    for call in manifest["calls"]:
        raw_file = snapshot / call["raw_file"]
        payload = json.loads(raw_file.read_text(encoding="utf-8"))
        cell = call["cell"]
        for raw in extract_records(payload):
            record = to_provider(raw, cell, raw_file)
            if not record:
                skipped += 1
                continue
            before = db.total_changes
            db.execute("""INSERT OR IGNORE INTO providers
                (provider_key,name,category,area,city,address,lat,lng,rating,review_count,phone,open_now,hours,source,mutation,raw_file)
                VALUES (:provider_key,:name,:category,:area,:city,:address,:lat,:lng,:rating,:review_count,:phone,:open_now,:hours,:source,:mutation,:raw_file)""", record)
            inserted += db.total_changes > before
    db.commit()
    total = db.execute("SELECT count(*) FROM providers").fetchone()[0]
    report = {"snapshot": str(snapshot), "inserted": inserted, "skipped_missing_name": skipped,
              "database_total": total, "real_records": db.execute("SELECT count(*) FROM providers WHERE source='real'").fetchone()[0]}
    report_path = DATA / "curation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    db.close()


if __name__ == "__main__":
    main()
