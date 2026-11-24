import argparse

from common import DATA, connect, create_db


def main():
    parser = argparse.ArgumentParser(description="Add explicitly labeled, deterministic stress records")
    parser.add_argument("--db", default=str(DATA / "corpus.sqlite"))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    db = create_db(connect(args.db))
    originals = db.execute("SELECT * FROM providers WHERE source='real' ORDER BY id LIMIT ?", (args.limit,)).fetchall()
    for ix, row in enumerate(originals):
        mutation = ("missing_phone", "near_duplicate", "wrong_category", "closed")[ix % 4]
        name = f"{row['name']} Services" if mutation == "near_duplicate" else row["name"]
        phone = "" if mutation == "missing_phone" else row["phone"]
        category = "Unrelated category" if mutation == "wrong_category" else row["category"]
        open_now = 0 if mutation == "closed" else row["open_now"]
        db.execute("""INSERT OR IGNORE INTO providers
          (provider_key,name,category,area,city,address,lat,lng,rating,review_count,phone,open_now,hours,source,mutation,raw_file)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'synthetic',?,?)""",
          (f"synthetic:{row['provider_key']}:{mutation}", name, category, row["area"], row["city"],
           row["address"], row["lat"], row["lng"], row["rating"], row["review_count"], phone,
           open_now, row["hours"], mutation, row["raw_file"]))
    db.commit()
    print(f"Added labeled mutations for up to {len(originals)} real records")
    db.close()


if __name__ == "__main__":
    main()
