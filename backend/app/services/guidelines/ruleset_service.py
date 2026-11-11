"""
Guideline Rule Set Service.
Handles validation, versioning, lineage tracking, provenance, and effective rule resolution.
Reference: Guideline Extraction Plan Section 7.6, Phase G8, Phase G9.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import ValidationError
from sqlalchemy import select, update, or_
from sqlalchemy.orm import Session

from app.db.models.guideline_rule import GuidelineRule
from app.db.models.project import Project
from app.services.guidelines.schema import GuidelineRuleSchema


class RuleValidationError(Exception):
    def __init__(self, code: str, message: str, errors: Any = None, unreviewed_fields: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors
        self.unreviewed_fields = unreviewed_fields or []


def has_any_rules(schema_obj: GuidelineRuleSchema) -> bool:
    """Checks if at least one rule property is set across all sections."""
    sections = [
        schema_obj.general,
        schema_obj.citation,
        schema_obj.layout,
        schema_obj.figures,
        schema_obj.submission,
        schema_obj.articleTypes,
        schema_obj.other,
    ]
    for s in sections:
        if s is not None:
            if isinstance(s, list) and len(s) > 0:
                return True
            elif hasattr(s, "model_dump"):
                d = s.model_dump(exclude_none=True)
                if d:
                    return True
    return False


def validate_rules_payload(raw_rules: Any) -> dict[str, Any]:
    """Validates raw rules dictionary against GuidelineRuleSchema and ensures non-empty."""
    if not isinstance(raw_rules, dict):
        raise RuleValidationError(code="INVALID_RULES", message="Rules must be a JSON object.")

    try:
        validated = GuidelineRuleSchema.model_validate(raw_rules)
    except ValidationError as ve:
        raise RuleValidationError(code="INVALID_RULES", message="Rules validation failed.", errors=ve.errors())

    if not has_any_rules(validated):
        raise RuleValidationError(code="NO_RULES", message="At least one rule must be provided.")

    return validated.model_dump(exclude_none=True)


def get_field_value_by_path(d: dict[str, Any], path: str) -> Any:
    """Gets a nested value by dot path (e.g. 'general.maxWords')."""
    parts = path.split(".")
    curr: Any = d
    for p in parts:
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        else:
            return None
    return curr


def check_unreviewed_low_confidence_fields(
    draft: dict[str, Any] | None,
    submitted_rules: dict[str, Any],
    acknowledged_fields: list[str],
) -> list[str]:
    """
    Returns a list of low-confidence draft fields that were neither acknowledged
    nor edited by the user (GE-RS-03, GE-RS-04, GE-RS-05).
    """
    if not draft or "fields" not in draft:
        return []

    ack_set = set(acknowledged_fields or [])
    unreviewed: list[str] = []

    fields_dict = draft.get("fields", {})
    if not isinstance(fields_dict, dict):
        return []

    for path, info in fields_dict.items():
        if isinstance(info, dict) and info.get("confidence") == "low":
            if path in ack_set:
                continue

            # Check if user edited the field value
            draft_val = info.get("value")
            submitted_val = get_field_value_by_path(submitted_rules, path)

            # If user value matches draft value exactly (or neither changed), it wasn't edited
            if submitted_val == draft_val:
                unreviewed.append(path)

    return sorted(unreviewed)


def build_ruleset_provenance(
    draft: dict[str, Any] | None,
    submitted_rules: dict[str, Any],
    previous_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Builds the provenance mapping for a rule set.
    For confirm: records evidence and confidence from draft, and marks edited: true if changed.
    For edit: keeps unchanged provenance, marks changed fields edited: true.
    """
    provenance: dict[str, Any] = {}
    draft_fields = (draft or {}).get("fields", {}) if isinstance(draft, dict) else {}
    prev_prov = previous_provenance or {}

    def _walk(obj: Any, prefix: str = ""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "schemaVersion":
                    continue
                path = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict) and k != "keywords":
                    _walk(v, path)
                else:
                    # Leaf field
                    if path in draft_fields:
                        df = draft_fields[path]
                        draft_val = df.get("value")
                        is_edited = (v != draft_val)
                        provenance[path] = {
                            "confidence": df.get("confidence", "high"),
                            "evidence": df.get("evidence"),
                            "edited": is_edited,
                        }
                    elif path in prev_prov:
                        # From previous version
                        old_entry = prev_prov[path]
                        # Check if value changed
                        provenance[path] = old_entry
                    else:
                        provenance[path] = {
                            "confidence": "high",
                            "evidence": None,
                            "edited": True,
                        }

    _walk(submitted_rules)
    return provenance


def resolve_effective_rule_for_journal(
    db: Session,
    user_id: int | None,
    journal_id: int,
) -> tuple[GuidelineRule | None, str | None]:
    """
    Resolves effective rule set for a catalog journal:
    1. User's active rule set for this journal (source: 'user')
    2. System active rule set for this journal (source: 'system')
    3. None
    Ad-hoc rule sets (journal_id=None) are never returned as a journal's effective rules (GE-RS-49).
    """
    if user_id is not None:
        user_rule = db.scalars(
            select(GuidelineRule).where(
                GuidelineRule.owner_user_id == user_id,
                GuidelineRule.journal_id == journal_id,
                GuidelineRule.is_active == True,
            )
        ).first()
        if user_rule:
            return user_rule, "user"

    system_rule = db.scalars(
        select(GuidelineRule).where(
            GuidelineRule.owner_user_id.is_(None),
            GuidelineRule.journal_id == journal_id,
            GuidelineRule.is_active == True,
        )
    ).first()
    if system_rule:
        return system_rule, "system"

    return None, None


def resolve_effective_rule_for_project(
    db: Session,
    project: Project,
) -> tuple[GuidelineRule | None, str | None]:
    """
    Resolves effective rule set for a project:
    1. project.guideline_rule_id (source: 'project')
    2. target journal user active rule set (source: 'user')
    3. target journal system active rule set (source: 'system')
    4. None
    """
    if project.guideline_rule_id:
        rule = db.get(GuidelineRule, project.guideline_rule_id)
        if rule:
            return rule, "project"

    from app.db.models.project_journal import ProjectJournal

    target_journal_id = db.scalar(
        select(ProjectJournal.journal_id).where(
            ProjectJournal.project_id == project.project_id,
            ProjectJournal.is_selected == True,
        )
    )

    if target_journal_id:
        return resolve_effective_rule_for_journal(db, project.user_id, target_journal_id)

    return None, None
