"""
Metric registry and evaluation logic for Journal Comparison.
Single source of truth for comparison rows, value extraction, completeness,
best-value computation, and difference detection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

GroupKey = Literal["overview", "fit", "impact", "speed", "cost", "scope", "requirements"]
ValueType = Literal[
    "text", "enum", "number", "integer", "percent", "currency", "link", "longtext", "list"
]
Direction = Literal["higher", "lower", "none"]


@dataclass(frozen=True)
class MetricRowDef:
    key: str
    label: str
    group: GroupKey
    type: ValueType
    direction: Direction
    alwaysShow: bool
    note: str
    completeness: bool


COMPARISON_GROUPS: list[tuple[GroupKey, str]] = [
    ("overview", "Overview"),
    ("fit", "Match to your paper"),
    ("impact", "Impact and ranking"),
    ("speed", "Speed and selectivity"),
    ("cost", "Cost"),
    ("scope", "Scope"),
    ("requirements", "Submission requirements"),
]

METRIC_REGISTRY: list[MetricRowDef] = [
    MetricRowDef(
        key="publisher",
        label="Publisher",
        group="overview",
        type="text",
        direction="none",
        alwaysShow=True,
        note="Journal table",
        completeness=True,
    ),
    MetricRowDef(
        key="issn",
        label="ISSN",
        group="overview",
        type="text",
        direction="none",
        alwaysShow=False,
        note="Journal table",
        completeness=True,
    ),
    MetricRowDef(
        key="subjectCategory",
        label="Subject area",
        group="overview",
        type="text",
        direction="none",
        alwaysShow=False,
        note="Assigned from controlled list",
        completeness=True,
    ),
    MetricRowDef(
        key="publishingModel",
        label="Publishing model",
        group="overview",
        type="enum",
        direction="none",
        alwaysShow=True,
        note="Open access, Hybrid, or Subscription",
        completeness=True,
    ),
    MetricRowDef(
        key="homepage",
        label="Journal website",
        group="overview",
        type="link",
        direction="none",
        alwaysShow=False,
        note="Official journal website",
        completeness=False,
    ),
    MetricRowDef(
        key="matchScore",
        label="Match to your paper",
        group="fit",
        type="integer",
        direction="higher",
        alwaysShow=True,
        note="Semantic similarity score for your active project (0 to 100)",
        completeness=False,
    ),
    MetricRowDef(
        key="quartile",
        label="Quartile (SJR)",
        group="impact",
        type="enum",
        direction="higher",
        alwaysShow=True,
        note="SCImago journal rank quartile, not Clarivate.",
        completeness=True,
    ),
    MetricRowDef(
        key="citeScore",
        label="CiteScore",
        group="impact",
        type="number",
        direction="higher",
        alwaysShow=False,
        note="Citation score from catalog",
        completeness=True,
    ),
    MetricRowDef(
        key="impactFactor",
        label="Impact Factor",
        group="impact",
        type="number",
        direction="higher",
        alwaysShow=False,
        note="Reported journal Impact Factor",
        completeness=True,
    ),
    MetricRowDef(
        key="sjr",
        label="SJR score",
        group="impact",
        type="number",
        direction="higher",
        alwaysShow=False,
        note="SCImago Journal Rank indicator",
        completeness=False,
    ),
    MetricRowDef(
        key="hIndex",
        label="h-index",
        group="impact",
        type="integer",
        direction="higher",
        alwaysShow=False,
        note="OpenAlex / SCImago h-index",
        completeness=False,
    ),
    MetricRowDef(
        key="citedness2yr",
        label="2-year mean citedness",
        group="impact",
        type="number",
        direction="higher",
        alwaysShow=False,
        note="OpenAlex 2-year mean citedness",
        completeness=False,
    ),
    MetricRowDef(
        key="apcUsd",
        label="Publication charge (APC)",
        group="cost",
        type="currency",
        direction="lower",
        alwaysShow=True,
        note="Article processing charge in USD",
        completeness=False,
    ),
    MetricRowDef(
        key="reviewWeeks",
        label="Review turnaround",
        group="speed",
        type="number",
        direction="lower",
        alwaysShow=True,
        note="Typical review time in weeks",
        completeness=True,
    ),
    MetricRowDef(
        key="acceptanceRate",
        label="Acceptance rate",
        group="speed",
        type="percent",
        direction="none",
        alwaysShow=True,
        note="Reported manuscript acceptance rate",
        completeness=True,
    ),
    MetricRowDef(
        key="aimsAndScope",
        label="Aims and scope",
        group="scope",
        type="longtext",
        direction="none",
        alwaysShow=True,
        note="Official journal scope text",
        completeness=False,
    ),
    MetricRowDef(
        key="rulesSource",
        label="Rules source",
        group="requirements",
        type="text",
        direction="none",
        alwaysShow=True,
        note="Active user ruleset or built-in seed rules",
        completeness=False,
    ),
    MetricRowDef(
        key="maxWords",
        label="Max word count",
        group="requirements",
        type="integer",
        direction="none",
        alwaysShow=True,
        note="Maximum manuscript word count",
        completeness=False,
    ),
    MetricRowDef(
        key="maxAbstractWords",
        label="Max abstract words",
        group="requirements",
        type="integer",
        direction="none",
        alwaysShow=True,
        note="Maximum abstract word count",
        completeness=False,
    ),
    MetricRowDef(
        key="citationStyle",
        label="Citation style",
        group="requirements",
        type="text",
        direction="none",
        alwaysShow=True,
        note="Required reference style",
        completeness=False,
    ),
    MetricRowDef(
        key="columns",
        label="Column layout",
        group="requirements",
        type="enum",
        direction="none",
        alwaysShow=True,
        note="Page column layout",
        completeness=False,
    ),
    MetricRowDef(
        key="requiredSections",
        label="Required sections",
        group="requirements",
        type="list",
        direction="none",
        alwaysShow=True,
        note="Mandatory manuscript section headings",
        completeness=False,
    ),
    MetricRowDef(
        key="keywords",
        label="Keywords count",
        group="requirements",
        type="text",
        direction="none",
        alwaysShow=True,
        note="Keyword count constraints",
        completeness=False,
    ),
]

METRIC_BY_KEY: dict[str, MetricRowDef] = {row.key: row for row in METRIC_REGISTRY}

COMPLETENESS_KEYS: tuple[str, ...] = tuple(
    row.key for row in METRIC_REGISTRY if row.completeness
)

QUARTILE_RANK: dict[str, int] = {
    "Q1": 4,
    "Q2": 3,
    "Q3": 2,
    "Q4": 1,
}

PUBLISHING_MODEL_MAP: dict[str, str] = {
    "open access": "Open access",
    "hybrid": "Hybrid",
    "subscription": "Subscription",
}


def _clean_text(val: Any) -> str | None:
    if val is None or isinstance(val, bool):
        return None
    s = str(val).strip()
    return s if s else None


def _clean_number(
    val: Any,
    *,
    as_int: bool = False,
    min_val: float | None = 0.0,
    max_val: float | None = None,
) -> int | float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        num = float(val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    if min_val is not None and num < min_val:
        return None
    if max_val is not None and num > max_val:
        return None
    if as_int:
        return int(round(num))
    return num


def format_keywords_range(kw: Any) -> str | None:
    """Formats a keywords constraint dict {min, max} for comparison display."""
    if not isinstance(kw, dict):
        return None
    kmin = _clean_number(kw.get("min"), as_int=True, min_val=0)
    kmax = _clean_number(kw.get("max"), as_int=True, min_val=0)
    if kmin is not None and kmax is not None:
        if kmin == kmax:
            return f"{kmin}"
        return f"{kmin} to {kmax}"
    if kmin is not None:
        return f"At least {kmin}"
    if kmax is not None:
        return f"Up to {kmax}"
    return None


def extract_metric_value(
    journal: Any,
    key: str,
    project_ctx: dict[str, Any] | None = None,
    req_ctx: tuple[Any, str | None] | None = None,
) -> Any:
    """
    Safely extracts and normalizes a single metric value for a journal.
    Uses getattr(..., None) so missing optional schema columns yield None cleanly.
    """
    if key == "publisher":
        return _clean_text(getattr(journal, "publisher", None))
    if key == "issn":
        return _clean_text(getattr(journal, "issn", None))
    if key == "subjectCategory":
        return _clean_text(getattr(journal, "subject_category", None))
    if key == "publishingModel":
        raw = _clean_text(getattr(journal, "open_access_type", None))
        if raw is None:
            return None
        return PUBLISHING_MODEL_MAP.get(raw.lower(), raw)
    if key == "homepage":
        return _clean_text(getattr(journal, "homepage_url", None))
    if key == "matchScore":
        if not project_ctx:
            return None
        return _clean_number(project_ctx.get("matchScore"), as_int=True, min_val=0, max_val=100)
    if key == "quartile":
        raw = _clean_text(getattr(journal, "quartile", None))
        if raw is None:
            return None
        upper = raw.upper()
        return upper if upper in QUARTILE_RANK else None
    if key == "citeScore":
        return _clean_number(getattr(journal, "citescore", None), min_val=0.0)
    if key == "impactFactor":
        # Never populated from citedness or citescore
        return _clean_number(getattr(journal, "impact_factor", None), min_val=0.0)
    if key == "sjr":
        return _clean_number(getattr(journal, "sjr", None), min_val=0.0)
    if key == "hIndex":
        return _clean_number(getattr(journal, "h_index", None), as_int=True, min_val=0)
    if key == "citedness2yr":
        return _clean_number(getattr(journal, "citedness_2yr", None), min_val=0.0)
    if key == "apcUsd":
        num = _clean_number(getattr(journal, "apc_usd", None), min_val=0.0)
        if num is None:
            return None
        return int(num) if float(num).is_integer() else round(float(num), 2)
    if key == "reviewWeeks":
        return _clean_number(getattr(journal, "review_weeks", None), min_val=0.0)
    if key == "acceptanceRate":
        return _clean_number(getattr(journal, "acceptance_rate", None), min_val=0.0, max_val=100.0)
    if key == "aimsAndScope":
        raw = getattr(journal, "aims_and_scope", None)
        if raw is None or isinstance(raw, bool):
            return None
        text = str(raw).replace("\\n", "\n").strip()
        return text if text else None

    # Requirements group (Part B)
    if key in (
        "rulesSource",
        "maxWords",
        "maxAbstractWords",
        "citationStyle",
        "columns",
        "requiredSections",
        "keywords",
    ):
        if not req_ctx:
            return None
        rule_obj, source_str = req_ctx
        if rule_obj is None:
            return None
        if key == "rulesSource":
            if source_str == "user":
                ver = getattr(rule_obj, "version", 1)
                return f"My rules (v{ver})"
            if source_str in ("system", "seed"):
                return "Built-in"
            return None

        rules_dict = getattr(rule_obj, "rules", None)
        if not isinstance(rules_dict, dict):
            return None
        general = rules_dict.get("general") or {}
        citation = rules_dict.get("citation") or {}
        layout = rules_dict.get("layout") or {}

        if key == "maxWords":
            return _clean_number(general.get("maxWords"), as_int=True, min_val=0)
        if key == "maxAbstractWords":
            return _clean_number(general.get("maxAbstractWords"), as_int=True, min_val=0)
        if key == "citationStyle":
            return _clean_text(citation.get("style"))
        if key == "columns":
            return _clean_text(layout.get("columns"))
        if key == "requiredSections":
            secs = general.get("requiredSections")
            if not isinstance(secs, list):
                return None
            cleaned = [s.strip() for s in secs if isinstance(s, str) and s.strip()]
            return cleaned if cleaned else None
        if key == "keywords":
            return format_keywords_range(general.get("keywords"))

    return None


def compute_completeness(journal: Any) -> dict[str, int]:
    """Counts available core metrics out of the 9 COMPLETENESS_KEYS."""
    available = 0
    for key in COMPLETENESS_KEYS:
        if extract_metric_value(journal, key) is not None:
            available += 1
    return {"available": available, "total": len(COMPLETENESS_KEYS)}


def _to_comparable_for_best(row_def: MetricRowDef, val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    if row_def.key == "quartile":
        rank = QUARTILE_RANK.get(str(val).strip().upper())
        return float(rank) if rank is not None else None
    if row_def.type in ("number", "integer", "percent", "currency"):
        try:
            num = float(val)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(num) or num < 0:
            return None
        if row_def.key in ("acceptanceRate", "matchScore") and num > 100:
            return None
        return round(num, 3)
    return None


def _to_comparable_for_equality(row_def: MetricRowDef, val: Any) -> Any:
    if val is None:
        return None
    if row_def.type == "list":
        if isinstance(val, list):
            return frozenset(str(item).strip().lower() for item in val if str(item).strip())
        return None
    if row_def.type in ("number", "integer", "percent", "currency"):
        try:
            num = float(val)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(num):
            return None
        return round(num, 3)
    return str(val).strip().lower()


def compute_row_evaluation(
    row_def: MetricRowDef,
    values: list[Any],
) -> tuple[bool, list[bool]]:
    """
    Computes (allSame, isBest_list) for a metric row across candidate journals.
    """
    if not values:
        return True, []

    # 1. allSame: count None as a value
    has_none = any(v is None for v in values)
    has_non_none = any(v is not None for v in values)
    if has_none and has_non_none:
        all_same = False
    elif not has_non_none:
        all_same = True
    else:
        eq_keys = [_to_comparable_for_equality(row_def, v) for v in values]
        first = eq_keys[0]
        all_same = all(k == first for k in eq_keys[1:])

    # 2. isBest
    n = len(values)
    best_flags = [False] * n
    if row_def.direction == "none":
        return all_same, best_flags

    comp_pairs: list[tuple[int, float]] = []
    for idx, val in enumerate(values):
        comp = _to_comparable_for_best(row_def, val)
        if comp is not None:
            comp_pairs.append((idx, comp))

    if len(comp_pairs) < 2:
        return all_same, best_flags

    distinct_vals = {comp for _, comp in comp_pairs}
    if len(distinct_vals) <= 1:
        return all_same, best_flags

    target = max(distinct_vals) if row_def.direction == "higher" else min(distinct_vals)
    for idx, comp in comp_pairs:
        if comp == target:
            best_flags[idx] = True

    return all_same, best_flags


def _format_iso_utc(dt: Any) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(dt)


def build_comparison_payload(
    journals: list[Any],
    *,
    project_ctx_map: dict[int, dict[str, Any]] | None = None,
    include_fit: bool = False,
    req_ctx_map: dict[int, tuple[Any, str | None]] | None = None,
    include_requirements: bool = False,
) -> dict[str, Any]:
    """
    Constructs the full GET /journals/compare response structure.
    """
    project_ctx_map = project_ctx_map or {}
    req_ctx_map = req_ctx_map or {}

    journal_headers: list[dict[str, Any]] = []
    for j in journals:
        jid = getattr(j, "journal_id", None)
        if include_fit:
            p_ctx = project_ctx_map.get(
                jid,
                {
                    "isShortlisted": False,
                    "isTarget": False,
                    "rawSimilarity": None,
                    "matchScore": None,
                },
            )
        else:
            p_ctx = None

        updated_dt = getattr(j, "metadata_updated_at", None) or getattr(j, "created_at", None)
        journal_headers.append(
            {
                "id": str(jid),
                "title": getattr(j, "journal_title", ""),
                "publisher": getattr(j, "publisher", ""),
                "homepageUrl": extract_metric_value(j, "homepage"),
                "metadataUpdatedAt": _format_iso_utc(updated_dt),
                "completeness": compute_completeness(j),
                "projectContext": p_ctx,
            }
        )

    groups_out: list[dict[str, str]] = []
    for g_key, g_label in COMPARISON_GROUPS:
        if g_key == "fit" and not include_fit:
            continue
        if g_key == "requirements" and not include_requirements:
            continue
        groups_out.append({"key": g_key, "label": g_label})

    rows_out: list[dict[str, Any]] = []
    for row_def in METRIC_REGISTRY:
        if row_def.group == "fit" and not include_fit:
            continue
        if row_def.group == "requirements" and not include_requirements:
            continue

        raw_values: list[Any] = []
        for j in journals:
            jid = getattr(j, "journal_id", None)
            p_ctx = project_ctx_map.get(jid) if include_fit else None
            r_ctx = req_ctx_map.get(jid) if include_requirements else None
            raw_values.append(
                extract_metric_value(j, row_def.key, project_ctx=p_ctx, req_ctx=r_ctx)
            )

        if not row_def.alwaysShow and all(v is None for v in raw_values):
            continue

        all_same, best_flags = compute_row_evaluation(row_def, raw_values)
        rows_out.append(
            {
                "key": row_def.key,
                "label": row_def.label,
                "group": row_def.group,
                "type": row_def.type,
                "direction": row_def.direction,
                "alwaysShow": row_def.alwaysShow,
                "note": row_def.note,
                "allSame": all_same,
                "values": [
                    {"value": val, "isBest": is_best}
                    for val, is_best in zip(raw_values, best_flags)
                ],
            }
        )

    return {
        "journals": journal_headers,
        "groups": groups_out,
        "rows": rows_out,
        "notes": [
            "N/A means the value is not available from our data sources.",
            "Quartile is based on SCImago SJR, not Clarivate.",
        ],
        "generatedAt": _format_iso_utc(datetime.now(timezone.utc)),
    }

