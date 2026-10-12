import argparse
import csv
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select, text
from app.db.session import SessionLocal
from app.db.models.journal import Journal

SEED_CSV_PATH = Path(__file__).resolve().parent.parent / "seed" / "journals.csv"

def parse_float(val: str) -> float | None:
    if not val or not val.strip():
        return None
    try:
        return float(val.strip())
    except ValueError:
        return None

def parse_int(val: str) -> int | None:
    if not val or not val.strip():
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None

def seed_journals(csv_path: Path = SEED_CSV_PATH, reset: bool = False):
    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading journals from {csv_path}...")
    inserted_count = 0
    updated_count = 0
    skipped_count = 0

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} entries in CSV. Starting upsert transaction...")

    with SessionLocal() as session:
        try:
            if reset:
                print("Resetting journals table (TRUNCATE CASCADE)...")
                session.execute(text("TRUNCATE TABLE journals RESTART IDENTITY CASCADE;"))
                session.flush()
            for idx, row in enumerate(rows, start=1):
                title = row.get("journal_title", "").strip()
                publisher = row.get("publisher", "").strip()
                issn = row.get("issn", "").strip() or None
                aims_and_scope = row.get("aims_and_scope", "").strip()

                if not title or not publisher or not aims_and_scope:
                    print(f"  [Row {idx}] Skipped: Missing required title, publisher, or aims_and_scope")
                    skipped_count += 1
                    continue

                subject_cat = row.get("subject_category", "").strip() or None
                citescore = parse_float(row.get("citescore", ""))
                impact_factor = parse_float(row.get("impact_factor", ""))
                quartile = row.get("quartile", "").strip() or None
                open_access = row.get("open_access_type", "").strip() or None
                review_weeks = parse_int(row.get("review_weeks", ""))
                acceptance_rate = parse_float(row.get("acceptance_rate", ""))

                # Range checks
                if review_weeks is not None and review_weeks < 0:
                    print(f"  [Row {idx}] Skipped: review_weeks ({review_weeks}) is negative")
                    skipped_count += 1
                    continue

                if acceptance_rate is not None and (acceptance_rate < 0 or acceptance_rate > 100):
                    print(f"  [Row {idx}] Skipped: acceptance_rate ({acceptance_rate}) outside 0-100")
                    skipped_count += 1
                    continue

                # Look up existing journal by ISSN (if present) or (title, publisher)
                existing = None
                if issn:
                    existing = session.execute(
                        select(Journal).where(Journal.issn == issn)
                    ).scalar_one_or_none()

                if not existing:
                    existing = session.execute(
                        select(Journal).where(
                            Journal.journal_title == title,
                            Journal.publisher == publisher,
                        )
                    ).scalar_one_or_none()

                if existing:
                    # Update fields
                    existing.journal_title = title
                    existing.publisher = publisher
                    existing.issn = issn
                    existing.subject_category = subject_cat
                    existing.citescore = citescore
                    existing.impact_factor = impact_factor
                    existing.quartile = quartile
                    existing.aims_and_scope = aims_and_scope
                    existing.open_access_type = open_access
                    existing.review_weeks = review_weeks
                    existing.acceptance_rate = acceptance_rate
                    updated_count += 1
                else:
                    new_journal = Journal(
                        journal_title=title,
                        publisher=publisher,
                        issn=issn,
                        subject_category=subject_cat,
                        citescore=citescore,
                        impact_factor=impact_factor,
                        quartile=quartile,
                        aims_and_scope=aims_and_scope,
                        open_access_type=open_access,
                        review_weeks=review_weeks,
                        acceptance_rate=acceptance_rate,
                    )
                    session.add(new_journal)
                    inserted_count += 1

            session.commit()
            print("Transaction committed successfully.")
            print(f"Summary: Inserted = {inserted_count}, Updated = {updated_count}, Skipped = {skipped_count}")
        except Exception as e:
            session.rollback()
            print(f"Error seeding journals (transaction rolled back): {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed journals from CSV.")
    parser.add_argument("--reset", action="store_true", help="Wipe/truncate existing journals before inserting")
    parser.add_argument("--csv", type=Path, default=SEED_CSV_PATH, help="Path to custom CSV file")
    args = parser.parse_args()

    seed_journals(csv_path=args.csv, reset=args.reset)
