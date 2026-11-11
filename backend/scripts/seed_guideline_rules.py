"""
Seed script for Hand-Verified System Guideline Rules.
Validates each file against the GuidelineRuleSchema and idempotently
inserts or updates system rule sets.
Reference: Guideline Extraction Plan Section 7.6, 10.13 (GE-RS-44).
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.guideline_rule import GuidelineRule
from app.db.models.journal import Journal
from app.services.guidelines.schema import GuidelineRuleSchema

logger = logging.getLogger("seed_guideline_rules")
DEFAULT_SEED_DIR = BACKEND_DIR / "seed" / "guideline_rules"


def load_and_validate_rule_file(file_path: Path) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{file_path.name}: Top-level JSON must be an object.")

    if not data.get("name"):
        raise ValueError(f"{file_path.name}: 'name' is required.")

    if not data.get("rules") or not isinstance(data.get("rules"), dict):
        raise ValueError(f"{file_path.name}: 'rules' object is required.")

    # Validate schema
    validated = GuidelineRuleSchema.model_validate(data["rules"])
    data["rules"] = validated.model_dump(exclude_none=True)
    return data


def resolve_journal(db: Session, title: str | None, issn: str | None) -> Journal | None:
    if issn:
        clean_issn = issn.strip()
        journal = db.scalars(select(Journal).where(Journal.issn == clean_issn)).first()
        if journal:
            return journal

    if title:
        clean_title = title.strip().lower()
        journal = db.scalars(select(Journal).where(Journal.journal_title.ilike(clean_title))).first()
        if journal:
            return journal

    return None


def seed_guideline_rules(
    db: Session | None = None,
    rules_dir: Path = DEFAULT_SEED_DIR,
    raise_on_error: bool = False,
) -> int:
    """
    Idempotently seeds guideline rules from JSON files in rules_dir into database.
    Returns number of seeded rule sets.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        if not rules_dir.exists():
            logger.warning(f"Seed directory {rules_dir} does not exist.")
            return 0

        json_files = sorted(rules_dir.glob("*.json"))
        seeded_count = 0

        for file_path in json_files:
            try:
                data = load_and_validate_rule_file(file_path)
            except Exception as e:
                logger.error(f"Failed to validate {file_path.name}: {e}")
                if raise_on_error:
                    raise
                continue

            journal_title = data.get("journalTitle")
            journal_issn = data.get("journalIssn")
            journal = resolve_journal(db, journal_title, journal_issn)
            journal_id = journal.journal_id if journal else None

            # Look for existing system rule set for this journal or name
            query = select(GuidelineRule).where(
                GuidelineRule.owner_user_id.is_(None),
            )
            if journal_id:
                query = query.where(GuidelineRule.journal_id == journal_id)
            else:
                query = query.where(GuidelineRule.name == data["name"])

            existing_rule = db.scalars(query).first()

            if existing_rule:
                existing_rule.name = data["name"]
                existing_rule.source_url = data.get("sourceUrl")
                existing_rule.rules = data["rules"]
                existing_rule.schema_version = data.get("schemaVersion", 1)
                existing_rule.is_active = True
                existing_rule.origin = "seed"
                existing_rule.provenance = {"seeded": True, "sourceFile": file_path.name}
            else:
                new_rule = GuidelineRule(
                    owner_user_id=None,
                    journal_id=journal_id,
                    name=data["name"],
                    origin="seed",
                    schema_version=data.get("schemaVersion", 1),
                    source_url=data.get("sourceUrl"),
                    rules=data["rules"],
                    provenance={"seeded": True, "sourceFile": file_path.name},
                    version=1,
                    is_active=True,
                    lineage_id=None,
                )
                db.add(new_rule)

            seeded_count += 1

        db.commit()
        return seeded_count
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Seed system guideline rules.")
    parser.add_argument("--dir", type=str, default=str(DEFAULT_SEED_DIR), help="Directory of rule JSON files")
    args = parser.parse_args()

    count = seed_guideline_rules(rules_dir=Path(args.dir), raise_on_error=True)
    print(f"Successfully seeded {count} system guideline rules.")
