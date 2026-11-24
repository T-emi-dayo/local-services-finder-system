"""Create 50 corpus-independent query prompts with provisional SQL labels for review."""
import argparse

from common import DATA, connect, jsonl_write

DETAILS = {
    "electrician": "There is a wiring issue at home",
    "plumber": "A sink is leaking",
    "mechanic": "My car needs repair",
    "salon": "I need a haircut and styling",
}
TEMPLATES = [
    "I need a {service} in {area}, {city}.",
    "Find a {service} in {area} that I can call.",
    "Which {service} in {area} has the strongest rating?",
    "Can you suggest someone for this: {details} Location: {area}, {city}.",
    "Are there any nearby {service} providers around {area}?",
]
UNANSWERABLE = "I need a chimney sweep in {area}, {city}."


def candidate_ids(db, service, area, city, phone=False, minimum_rating=None):
    pattern = f"%{service.casefold()}%"
    sql = """SELECT provider_key FROM providers WHERE source='real'
             AND lower(area)=lower(?) AND lower(city)=lower(?)
             AND (lower(category) LIKE ? OR lower(name) LIKE ?)"""
    args = [area, city, pattern, pattern]
    if phone:
        sql += " AND coalesce(phone,'') <> ''"
    if minimum_rating is not None:
        sql += " AND rating >= ?"
        args.append(minimum_rating)
    return [r[0] for r in db.execute(sql, args)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DATA / "corpus.sqlite"))
    parser.add_argument("--out", default=str(DATA / "queries_draft.jsonl"))
    args = parser.parse_args()
    db = connect(args.db)
    cells = [("electrician", "Yaba", "Lagos", "golden"), ("plumber", "Yaba", "Lagos", "golden"),
             ("mechanic", "Yaba", "Lagos", "test"), ("salon", "Yaba", "Lagos", "test"),
             ("electrician", "Lekki", "Lagos", "test"), ("plumber", "Lekki", "Lagos", "test"),
             ("mechanic", "Lekki", "Lagos", "golden"), ("salon", "Lekki", "Lagos", "golden")]
    rows = []
    for service, area, city, split in cells:
        for index, template in enumerate(TEMPLATES):
            ids = candidate_ids(db, service, area, city, phone=(index == 1), minimum_rating=(4.0 if index == 2 else None))
            rows.append({"query_id": f"q{len(rows)+1:02d}", "query_text": template.format(service=service, area=area, city=city, details=DETAILS[service]),
                         "service_type": service.title(), "location_city": city, "location_area": area,
                         "urgency": "NOT_URGENT", "budget": "NO_BUDGET", "additional_details": DETAILS[service] if index == 3 else "",
                         "expected_provider_ids": ids, "acceptable_provider_ids": [], "no_result_expected": not ids,
                         "ground_truth_sql": "service/category LIKE ? AND area=? AND city=?" + (" AND phone present" if index == 1 else " AND rating>=4" if index == 2 else ""),
                         "split": split, "review_status": "pending", "review_notes": "Verify provider relevance and SQL-derived labels before compiling golden."})
        rows.append({"query_id": f"q{len(rows)+1:02d}", "query_text": UNANSWERABLE.format(area=area, city=city),
                     "service_type": "Chimney sweep", "location_city": city, "location_area": area,
                     "urgency": "NOT_URGENT", "budget": "NO_BUDGET", "additional_details": "",
                     "expected_provider_ids": [], "acceptable_provider_ids": [], "no_result_expected": True,
                     "ground_truth_sql": "category/name LIKE '%chimney sweep%' AND area=? AND city=?",
                     "split": split, "review_status": "pending", "review_notes": "Verify the frozen corpus truly has no matching provider."})
    # Two extra hard no-result cases reach the planned 50 queries and remain held out.
    for service in ("lighthouse keeper", "spaceship mechanic"):
        rows.append({"query_id": f"q{len(rows)+1:02d}", "query_text": f"Find a {service} in Lagos.",
                     "service_type": service.title(), "location_city": "Lagos", "location_area": "Yaba",
                     "urgency": "NOT_URGENT", "budget": "NO_BUDGET", "additional_details": "",
                     "expected_provider_ids": [], "acceptable_provider_ids": [], "no_result_expected": True,
                     "ground_truth_sql": "category/name LIKE service AND city=? AND area=?",
                     "split": "test", "review_status": "pending", "review_notes": "Verify no matches in frozen corpus."})
    jsonl_write(args.out, rows)
    print(f"Created {len(rows)} query drafts: {sum(r['split']=='golden' for r in rows)} golden candidates, {sum(r['split']=='test' for r in rows)} test candidates")
    db.close()


if __name__ == "__main__":
    main()
