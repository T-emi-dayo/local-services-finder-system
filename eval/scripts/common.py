import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "eval" / "data"


def jsonl_read(path):
    with open(path, encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def jsonl_write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def connect(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def extract_records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "results", "businesses"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def to_provider(raw, cell, raw_file):
    name = raw.get("name") or raw.get("title")
    if not name:
        return None
    subtypes = raw.get("subtypes") or raw.get("types") or raw.get("category") or []
    if not isinstance(subtypes, list):
        subtypes = [subtypes]
    phone = raw.get("phone_number") or raw.get("phone")
    if isinstance(phone, list):
        phone = ", ".join(str(p) for p in phone)
    return {
        "provider_key": str(raw.get("business_id") or raw.get("google_id") or raw.get("place_id") or normalize_text(name)),
        "name": str(name), "category": ", ".join(map(str, subtypes)),
        "area": cell.get("area", ""), "city": cell.get("city", ""),
        "address": raw.get("full_address") or raw.get("address") or "",
        "lat": raw.get("latitude") or raw.get("lat"),
        "lng": raw.get("longitude") or raw.get("lng"),
        "rating": raw.get("rating"),
        "review_count": raw.get("review_count") or raw.get("reviews"),
        "phone": phone or "", "open_now": raw.get("open_now"),
        "hours": json.dumps(raw.get("working_hours") or raw.get("hours"), ensure_ascii=False) if raw.get("working_hours") or raw.get("hours") else "",
        "source": "real", "mutation": None, "raw_file": str(raw_file),
    }


def load_snapshot_providers(snapshot_path):
    """Load and normalize real provider rows from saved snapshot manifests/JSON."""
    snapshot_path = Path(snapshot_path)
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot path does not exist: {snapshot_path}")
    if snapshot_path.is_file():
        manifests = [snapshot_path] if snapshot_path.name.lower() == "manifest.json" else []
    else:
        manifests = sorted(snapshot_path.rglob("manifest.json"))
    if not manifests:
        raise ValueError(f"No manifest.json files found under {snapshot_path}; raw calls need cell metadata from a manifest")

    providers = {}
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for call in manifest.get("calls", []):
            raw_file = manifest_path.parent / call["raw_file"]
            payload = json.loads(raw_file.read_text(encoding="utf-8"))
            cell = call.get("cell") or {}
            for raw in extract_records(payload):
                record = to_provider(raw, cell, raw_file)
                if not record:
                    continue
                key = (record["provider_key"], record["area"], record["city"])
                providers.setdefault(key, record)
    if not providers:
        raise ValueError(f"No provider records found in snapshots at {snapshot_path}")
    return list(providers.values())


def create_db(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS providers (
      id INTEGER PRIMARY KEY, provider_key TEXT NOT NULL, name TEXT NOT NULL,
      category TEXT, area TEXT, city TEXT, address TEXT, lat REAL, lng REAL,
      rating REAL, review_count INTEGER, phone TEXT, open_now, hours TEXT,
      source TEXT NOT NULL CHECK(source IN ('real','synthetic')),
      mutation TEXT, raw_file TEXT, UNIQUE(provider_key, area, city, source, mutation)
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS providers_fts USING fts5(name, category, area, city, address, content='providers', content_rowid='id');
    CREATE TRIGGER IF NOT EXISTS providers_ai AFTER INSERT ON providers BEGIN
      INSERT INTO providers_fts(rowid,name,category,area,city,address) VALUES(new.id,new.name,new.category,new.area,new.city,new.address);
    END;
    CREATE TRIGGER IF NOT EXISTS providers_ad AFTER DELETE ON providers BEGIN
      INSERT INTO providers_fts(providers_fts,rowid,name,category,area,city,address) VALUES('delete',old.id,old.name,old.category,old.area,old.city,old.address);
    END;
    """)
    return db
