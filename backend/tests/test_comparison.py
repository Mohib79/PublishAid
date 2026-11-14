"""
Comprehensive unit and integration tests for Journal Comparison (Plan 5: Part A & Part B).
Covers JC-REG, JC-BST, JC-CMP, JC-PRJ, JC-REQ, and JC-CAT suites.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.core.security import create_access_token
from app.db.models.guideline_rule import GuidelineRule
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.project_journal import ProjectJournal
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.services.comparison.registry import (
    COMPLETENESS_KEYS,
    METRIC_BY_KEY,
    METRIC_REGISTRY,
    build_comparison_payload,
    compute_completeness,
    compute_row_evaluation,
    extract_metric_value,
    format_keywords_range,
)
from app.services.guidelines.ruleset_service import resolve_effective_rules_for_journals
from app.services.matching import to_match_score


def _make_dummy_journal(**overrides) -> SimpleNamespace:
    defaults = {
        "journal_id": 1,
        "journal_title": "Sample Journal",
        "publisher": "IEEE",
        "issn": "1234-5678",
        "subject_category": "Computer Vision",
        "open_access_type": "Hybrid",
        "quartile": "Q1",
        "citescore": 12.5,
        "impact_factor": 6.4,
        "review_weeks": 12.0,
        "acceptance_rate": 18.0,
        "aims_and_scope": "Original research in vision and pattern recognition.",
        "created_at": datetime(2026, 10, 11, 17, 55, 23, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# =============================================================================
# 8.1 Metric Registry Unit Tests (No DB required)
# =============================================================================


def test_jc_reg_01_registry_has_valid_groups_and_types():
    valid_groups = {"overview", "fit", "impact", "speed", "cost", "scope", "requirements"}
    valid_types = {
        "text", "enum", "number", "integer", "percent", "currency", "link", "longtext", "list"
    }
    valid_dirs = {"higher", "lower", "none"}

    expected_keys = {
        "publisher", "issn", "subjectCategory", "publishingModel", "homepage",
        "matchScore", "quartile", "citeScore", "impactFactor", "sjr", "hIndex",
        "citedness2yr", "apcUsd", "reviewWeeks", "acceptanceRate", "aimsAndScope",
        "rulesSource", "maxWords", "maxAbstractWords", "citationStyle",
        "columns", "requiredSections", "keywords",
    }
    assert expected_keys.issubset({r.key for r in METRIC_REGISTRY})
    for row in METRIC_REGISTRY:
        assert row.group in valid_groups
        assert row.type in valid_types
        assert row.direction in valid_dirs


def test_jc_reg_02_every_row_has_label_and_unique_key():
    keys = [r.key for r in METRIC_REGISTRY]
    assert len(keys) == len(set(keys))
    for row in METRIC_REGISTRY:
        assert row.label and row.label.strip()


def test_jc_reg_03_value_extraction_all_fields_populated():
    j = _make_dummy_journal(
        homepage_url="https://example.org/journal",
        sjr=2.45,
        h_index=140,
        citedness_2yr=9.12,
        apc_usd=3500,
    )
    assert extract_metric_value(j, "publisher") == "IEEE"
    assert extract_metric_value(j, "issn") == "1234-5678"
    assert extract_metric_value(j, "subjectCategory") == "Computer Vision"
    assert extract_metric_value(j, "publishingModel") == "Hybrid"
    assert extract_metric_value(j, "homepage") == "https://example.org/journal"
    assert extract_metric_value(j, "quartile") == "Q1"
    assert extract_metric_value(j, "citeScore") == 12.5
    assert extract_metric_value(j, "impactFactor") == 6.4
    assert extract_metric_value(j, "sjr") == 2.45
    assert extract_metric_value(j, "hIndex") == 140
    assert extract_metric_value(j, "citedness2yr") == 9.12
    assert extract_metric_value(j, "apcUsd") == 3500
    assert extract_metric_value(j, "reviewWeeks") == 12.0
    assert extract_metric_value(j, "acceptanceRate") == 18.0
    assert "Original research" in extract_metric_value(j, "aimsAndScope")


def test_jc_reg_04_missing_optional_attributes_return_none():
    j = _make_dummy_journal()
    # SimpleNamespace has no homepage_url, sjr, h_index, citedness_2yr, apc_usd
    assert extract_metric_value(j, "homepage") is None
    assert extract_metric_value(j, "sjr") is None
    assert extract_metric_value(j, "hIndex") is None
    assert extract_metric_value(j, "citedness2yr") is None
    assert extract_metric_value(j, "apcUsd") is None


def test_jc_reg_05_publishing_model_normalizes_open_access_casing():
    j = _make_dummy_journal(open_access_type="Open Access")
    assert extract_metric_value(j, "publishingModel") == "Open access"
    j2 = _make_dummy_journal(open_access_type="  hybrid ")
    assert extract_metric_value(j2, "publishingModel") == "Hybrid"
    j3 = _make_dummy_journal(open_access_type="SUBSCRIPTION")
    assert extract_metric_value(j3, "publishingModel") == "Subscription"


def test_jc_reg_06_impact_factor_independent_of_citedness():
    j = _make_dummy_journal(impact_factor=None, citedness_2yr=8.75, citescore=15.0)
    assert extract_metric_value(j, "impactFactor") is None
    assert extract_metric_value(j, "citedness2yr") == 8.75


def test_jc_reg_07_citedness_label_does_not_mention_impact_factor():
    row = METRIC_BY_KEY["citedness2yr"]
    assert "impact factor" not in row.label.lower()
    assert "impact factor" not in row.note.lower()


def test_jc_reg_08_and_09_quartile_ranks_and_unexpected_values():
    _, best = compute_row_evaluation(METRIC_BY_KEY["quartile"], ["Q3", "Q1", "Q2", "Q4"])
    assert best == [False, True, False, False]

    j_bad = _make_dummy_journal(quartile="Q5")
    j_empty = _make_dummy_journal(quartile="   ")
    assert extract_metric_value(j_bad, "quartile") is None
    assert extract_metric_value(j_empty, "quartile") is None


def test_jc_reg_10_11_12_hidden_row_logic():
    # j1 & j2 both lack homepage, sjr, hIndex, citedness2yr, apcUsd, and impactFactor
    # but impactFactor has alwaysShow=False while apcUsd has alwaysShow=True
    j1 = _make_dummy_journal(journal_id=1, impact_factor=None, issn="1111-1111")
    j2 = _make_dummy_journal(journal_id=2, impact_factor=None, issn=None)

    payload = build_comparison_payload([j1, j2])
    row_keys = {r["key"] for r in payload["rows"]}

    # JC-REG-10: impactFactor is alwaysShow=False and all None -> omitted
    assert "impactFactor" not in row_keys
    # JC-REG-11: apcUsd is alwaysShow=True and all None -> kept
    assert "apcUsd" in row_keys
    # JC-REG-12: issn is alwaysShow=False and j1 has a value -> kept
    assert "issn" in row_keys


def test_jc_reg_13_and_14_completeness_counting():
    assert "matchScore" not in COMPLETENESS_KEYS
    assert "aimsAndScope" not in COMPLETENESS_KEYS
    assert len(COMPLETENESS_KEYS) == 9

    j_full = _make_dummy_journal()
    assert compute_completeness(j_full) == {"available": 9, "total": 9}

    j_empty = SimpleNamespace(
        journal_id=10,
        journal_title="Empty",
        publisher="",
        issn=None,
        subject_category="   ",
        open_access_type=None,
        quartile=None,
        citescore=None,
        impact_factor=None,
        review_weeks=None,
        acceptance_rate=None,
        aims_and_scope="Has scope only",
    )
    assert compute_completeness(j_empty) == {"available": 0, "total": 9}


def test_jc_reg_15_whitespace_text_treated_as_none():
    j = _make_dummy_journal(publisher="   ", issn="", subject_category="\t\n", aims_and_scope="   ")
    assert extract_metric_value(j, "publisher") is None
    assert extract_metric_value(j, "issn") is None
    assert extract_metric_value(j, "subjectCategory") is None
    assert extract_metric_value(j, "aimsAndScope") is None


# =============================================================================
# 8.2 Best Value & Differences Logic Tests (No DB required)
# =============================================================================


def test_jc_bst_01_higher_direction():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["citeScore"], [1.2, 2.1, 1.9])
    assert all_same is False
    assert best == [False, True, False]


def test_jc_bst_02_lower_direction_apc():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["apcUsd"], [3500, 0, 2000])
    assert all_same is False
    assert best == [False, True, False]


def test_jc_bst_03_tie_at_optimum():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["citeScore"], [2.1, 2.1, 1.0])
    assert all_same is False
    assert best == [True, True, False]


def test_jc_bst_04_all_values_equal():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["citeScore"], [5.0, 5.0, 5.0])
    assert all_same is True
    assert best == [False, False, False]


def test_jc_bst_05_only_one_value():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["citeScore"], [None, 5.0, None])
    assert all_same is False
    assert best == [False, False, False]


def test_jc_bst_06_two_values_and_one_na():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["citeScore"], [8.0, None, 12.0])
    assert all_same is False
    assert best == [False, False, True]


def test_jc_bst_07_and_12_all_na():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["apcUsd"], [None, None, None])
    assert all_same is True
    assert best == [False, False, False]


def test_jc_bst_08_none_direction():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["acceptanceRate"], [10.0, 50.0])
    assert all_same is False
    assert best == [False, False]

    all_same_p, best_p = compute_row_evaluation(METRIC_BY_KEY["publisher"], ["IEEE", "ACM"])
    assert all_same_p is False
    assert best_p == [False, False]


def test_jc_bst_09_quartile_comparison():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["quartile"], ["Q2", "Q1", "Q3"])
    assert all_same is False
    assert best == [False, True, False]


def test_jc_bst_10_rounding_to_3_decimals():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["sjr"], [1.2341, 1.2342])
    assert all_same is True
    assert best == [False, False]


def test_jc_bst_11_all_same_one_na_and_one_number():
    all_same, _ = compute_row_evaluation(METRIC_BY_KEY["citeScore"], [None, 5.0])
    assert all_same is False


def test_jc_bst_13_text_case_insensitive_trim():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["publisher"], [" IEEE ", "ieee"])
    assert all_same is True
    assert best == [False, False]


def test_jc_bst_14_apc_zero_vs_null():
    j_free = _make_dummy_journal(apc_usd=0)
    j_unknown = _make_dummy_journal(apc_usd=None)
    v_free = extract_metric_value(j_free, "apcUsd")
    v_unknown = extract_metric_value(j_unknown, "apcUsd")
    assert v_free == 0
    assert v_unknown is None
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["apcUsd"], [v_free, v_unknown])
    assert all_same is False
    assert best == [False, False]


def test_jc_bst_15_decimal_review_weeks():
    all_same, best = compute_row_evaluation(METRIC_BY_KEY["reviewWeeks"], [5.3, 12.0])
    assert all_same is False
    assert best == [True, False]


def test_jc_bst_16_negative_and_out_of_range_values():
    j_neg = _make_dummy_journal(citescore=-2.0, acceptance_rate=105.0, review_weeks=-1.0)
    assert extract_metric_value(j_neg, "citeScore") is None
    assert extract_metric_value(j_neg, "acceptanceRate") is None
    assert extract_metric_value(j_neg, "reviewWeeks") is None

    # Direct evaluation guard
    _, best = compute_row_evaluation(METRIC_BY_KEY["reviewWeeks"], [-5.0, 10.0])
    assert best == [False, False]


def test_jc_bst_17_list_rows_set_equality():
    row = METRIC_BY_KEY["requiredSections"]
    all_same, best = compute_row_evaluation(
        row,
        [["Abstract", "Introduction", "Methods"], ["methods", "Abstract", "INTRODUCTION"]],
    )
    assert all_same is True
    assert best == [False, False]

    all_same_diff, _ = compute_row_evaluation(
        row,
        [["Abstract", "Introduction"], ["Abstract", "Conclusion"]],
    )
    assert all_same_diff is False


# =============================================================================
# DB Fixtures for Integration Tests
# =============================================================================


@pytest.fixture
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def users(db_session):
    u1 = User(
        full_name="Compare User A",
        email="compare_user_a@example.com",
        password_hash="fakehash",
    )
    u2 = User(
        full_name="Compare User B",
        email="compare_user_b@example.com",
        password_hash="fakehash",
    )
    db_session.add_all([u1, u2])
    db_session.flush()
    t1 = create_access_token(u1.user_id)
    t2 = create_access_token(u2.user_id)
    return (u1, {"Authorization": f"Bearer {t1}"}), (u2, {"Authorization": f"Bearer {t2}"})


@pytest.fixture
def cmp_journals(db_session):
    j1 = Journal(
        journal_title="Alpha Vision Journal",
        publisher="IEEE",
        issn="9001-0001",
        subject_category="Computer Vision",
        citescore=21.7,
        impact_factor=15.3,
        quartile="Q1",
        aims_and_scope="Computer vision and image processing.",
        open_access_type="Open Access",
        review_weeks=5.3,
        acceptance_rate=16.0,
    )
    j2 = Journal(
        journal_title="Beta Pattern Journal",
        publisher="Elsevier",
        issn="9001-0002",
        subject_category="Artificial Intelligence",
        citescore=17.3,
        impact_factor=9.1,
        quartile="Q1",
        aims_and_scope="Pattern recognition and learning algorithms.",
        open_access_type="Hybrid",
        review_weeks=12.0,
        acceptance_rate=15.0,
    )
    j3 = Journal(
        journal_title="Gamma Systems Journal",
        publisher="ACM",
        issn="9001-0003",
        subject_category="Software Engineering",
        citescore=7.2,
        impact_factor=3.6,
        quartile="Q2",
        aims_and_scope="Software systems and architecture.",
        open_access_type="Subscription",
        review_weeks=16.0,
        acceptance_rate=22.0,
    )
    j4 = Journal(
        journal_title="Delta Networks Journal",
        publisher="Springer",
        issn="9001-0004",
        subject_category="Computer Networks",
        citescore=5.1,
        impact_factor=2.2,
        quartile="Q3",
        aims_and_scope="Networking and distributed systems.",
        open_access_type="Hybrid",
        review_weeks=18.0,
        acceptance_rate=28.0,
    )
    j5 = Journal(
        journal_title="Epsilon Theory Journal",
        publisher="Springer",
        issn="9001-0005",
        subject_category="Theoretical Computer Science",
        citescore=4.0,
        impact_factor=1.5,
        quartile="Q4",
        aims_and_scope="Algorithms and complexity theory.",
        open_access_type="Subscription",
        review_weeks=20.0,
        acceptance_rate=30.0,
    )
    db_session.add_all([j1, j2, j3, j4, j5])
    db_session.flush()
    return [j1, j2, j3, j4, j5]


# =============================================================================
# 8.3 Compare Endpoint Validation & Precedence Tests
# =============================================================================


def test_jc_cmp_01_to_03_valid_2_3_4_journals(client, users, cmp_journals):
    (_, headers), _ = users
    ids2 = f"{cmp_journals[0].journal_id},{cmp_journals[1].journal_id}"
    r2 = client.get(f"/journals/compare?ids={ids2}", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()["journals"]) == 2

    ids3 = f"{ids2},{cmp_journals[2].journal_id}"
    r3 = client.get(f"/journals/compare?ids={ids3}", headers=headers)
    assert r3.status_code == 200
    assert len(r3.json()["journals"]) == 3

    ids4 = f"{ids3},{cmp_journals[3].journal_id}"
    r4 = client.get(f"/journals/compare?ids={ids4}", headers=headers)
    assert r4.status_code == 200
    assert len(r4.json()["journals"]) == 4


def test_jc_cmp_04_to_06_validation_counts(client, users, cmp_journals):
    (_, headers), _ = users
    ids5 = ",".join(str(j.journal_id) for j in cmp_journals[:5])
    r5 = client.get(f"/journals/compare?ids={ids5}", headers=headers)
    assert r5.status_code == 422

    r1 = client.get(f"/journals/compare?ids={cmp_journals[0].journal_id}", headers=headers)
    assert r1.status_code == 422

    r_empty = client.get("/journals/compare?ids=", headers=headers)
    assert r_empty.status_code == 422

    r_omitted = client.get("/journals/compare", headers=headers)
    assert r_omitted.status_code == 422


def test_jc_cmp_07_and_08_duplicate_ids(client, users, cmp_journals):
    (_, headers), _ = users
    id1 = cmp_journals[0].journal_id
    id2 = cmp_journals[1].journal_id

    r_ok = client.get(f"/journals/compare?ids={id1},{id1},{id2}", headers=headers)
    assert r_ok.status_code == 200
    data = r_ok.json()
    assert [j["id"] for j in data["journals"]] == [str(id1), str(id2)]

    r_bad = client.get(f"/journals/compare?ids={id1},{id1}", headers=headers)
    assert r_bad.status_code == 422


def test_jc_cmp_09_to_12_malformed_and_limits(client, users, cmp_journals):
    (_, headers), _ = users
    id1 = cmp_journals[0].journal_id
    id2 = cmp_journals[1].journal_id

    # Non-numeric
    assert client.get(f"/journals/compare?ids={id1},abc", headers=headers).status_code == 422
    # Negative, zero, overflow
    assert client.get(f"/journals/compare?ids=-1,{id1}", headers=headers).status_code == 422
    assert client.get(f"/journals/compare?ids=0,{id1}", headers=headers).status_code == 422
    assert client.get(f"/journals/compare?ids=999999999999,{id1}", headers=headers).status_code == 422

    # Whitespace & trailing comma
    r_ws = client.get(f"/journals/compare?ids= {id1} , {id2}, ", headers=headers)
    assert r_ws.status_code == 200
    assert [j["id"] for j in r_ws.json()["journals"]] == [str(id1), str(id2)]

    # More than 20 raw tokens -> rejected prior to DB query
    many = ",".join(str(i) for i in range(1, 25))
    assert client.get(f"/journals/compare?ids={many}", headers=headers).status_code == 422

    # Unknown include parameter
    assert (
        client.get(f"/journals/compare?ids={id1},{id2}&include=unknown", headers=headers).status_code
        == 422
    )


def test_jc_cmp_13_unknown_id_returns_404_with_missing_ids(client, users, cmp_journals):
    (_, headers), _ = users
    id1 = cmp_journals[0].journal_id
    res = client.get(f"/journals/compare?ids={id1},999998", headers=headers)
    assert res.status_code == 404
    body = res.json()
    assert body["detail"] == "Journal not found"
    assert body["missingIds"] == ["999998"]


def test_jc_cmp_14_requires_auth(client, cmp_journals):
    ids2 = f"{cmp_journals[0].journal_id},{cmp_journals[1].journal_id}"
    assert client.get(f"/journals/compare?ids={ids2}").status_code == 401


def test_jc_cmp_15_16_17_order_camel_case_and_route_precedence(client, users, cmp_journals):
    (_, headers), _ = users
    id1 = cmp_journals[0].journal_id
    id2 = cmp_journals[1].journal_id
    # Request reversed order
    res = client.get(f"/journals/compare?ids={id2},{id1}", headers=headers)
    assert res.status_code == 200
    body = res.json()

    # Exact requested column order
    assert [j["id"] for j in body["journals"]] == [str(id2), str(id1)]
    assert all(isinstance(j["id"], str) for j in body["journals"])

    # Verify camelCase keys and Open Access normalization
    pm_row = next(r for r in body["rows"] if r["key"] == "publishingModel")
    assert pm_row["values"][0]["value"] == "Hybrid"
    assert pm_row["values"][1]["value"] == "Open access"
    assert "allSame" in pm_row
    assert "alwaysShow" in pm_row

    # Numeric path /{journal_id} still works alongside /compare
    res_single = client.get(f"/journals/{id1}", headers=headers)
    assert res_single.status_code == 200
    assert res_single.json()["id"] == str(id1)


# =============================================================================
# 8.4 Project Context Tests (Private data & isolation)
# =============================================================================


def test_jc_prj_01_to_07_project_context_and_isolation(client, db_session, users, cmp_journals):
    (u1, h1), (u2, h2) = users
    j1, j2, j3 = cmp_journals[0], cmp_journals[1], cmp_journals[2]

    proj_a = Project(user_id=u1.user_id, project_title="Project A", status="draft")
    proj_b = Project(user_id=u2.user_id, project_title="Project B", status="draft")
    db_session.add_all([proj_a, proj_b])
    db_session.flush()

    pj1 = ProjectJournal(
        project_id=proj_a.project_id,
        journal_id=j1.journal_id,
        similarity_score=0.865,
        is_shortlisted=True,
        is_selected=True,
    )
    pj2 = ProjectJournal(
        project_id=proj_a.project_id,
        journal_id=j2.journal_id,
        similarity_score=0.81,
        is_shortlisted=True,
        is_selected=False,
    )
    # j3 is NOT in Project A's ProjectJournal
    db_session.add_all([pj1, pj2])
    db_session.flush()

    ids3 = f"{j1.journal_id},{j2.journal_id},{j3.journal_id}"

    # JC-PRJ-01: No projectId
    res_no_proj = client.get(f"/journals/compare?ids={ids3}", headers=h1)
    assert res_no_proj.status_code == 200
    b0 = res_no_proj.json()
    assert all(j["projectContext"] is None for j in b0["journals"])
    assert "fit" not in [g["key"] for g in b0["groups"]]

    # JC-PRJ-02..05: With User A's projectId
    res_proj = client.get(f"/journals/compare?ids={ids3}&projectId={proj_a.project_id}", headers=h1)
    assert res_proj.status_code == 200
    b1 = res_proj.json()
    assert "fit" in [g["key"] for g in b1["groups"]]

    ctx1, ctx2, ctx3 = (
        b1["journals"][0]["projectContext"],
        b1["journals"][1]["projectContext"],
        b1["journals"][2]["projectContext"],
    )
    assert ctx1["isShortlisted"] is True
    assert ctx1["isTarget"] is True
    assert ctx1["matchScore"] == to_match_score(0.865) == 63

    assert ctx2["isShortlisted"] is True
    assert ctx2["isTarget"] is False
    assert ctx2["matchScore"] == to_match_score(0.81) == 39

    assert ctx3["isShortlisted"] is False
    assert ctx3["isTarget"] is False
    assert ctx3["matchScore"] is None

    match_row = next(r for r in b1["rows"] if r["key"] == "matchScore")
    assert [v["value"] for v in match_row["values"]] == [63, 39, None]
    assert [v["isBest"] for v in match_row["values"]] == [True, False, False]

    # JC-PRJ-06 & 07: Nonexistent or foreign projectId returns 404
    assert client.get(f"/journals/compare?ids={ids3}&projectId=999999", headers=h1).status_code == 404
    assert client.get(f"/journals/compare?ids={ids3}&projectId={proj_a.project_id}", headers=h2).status_code == 404


# =============================================================================
# 8.5 Requirements Rows Tests (Part B)
# =============================================================================


def test_jc_req_01_to_07_requirements_and_single_query(client, db_session, users, cmp_journals):
    (u1, h1), (u2, h2) = users
    j1, j2, j3 = cmp_journals[0], cmp_journals[1], cmp_journals[2]

    # j1: system seed rule + User 1 custom rule + User 2 custom rule
    sys_j1 = GuidelineRule(
        owner_user_id=None,
        journal_id=j1.journal_id,
        name="System J1",
        origin="seed",
        version=1,
        is_active=True,
        rules={"general": {"maxWords": 8000}, "citation": {"style": "IEEE"}},
    )
    user1_j1 = GuidelineRule(
        owner_user_id=u1.user_id,
        journal_id=j1.journal_id,
        name="User 1 J1",
        origin="manual",
        version=3,
        is_active=True,
        rules={
            "general": {
                "maxWords": 6500,
                "maxAbstractWords": 250,
                "keywords": {"min": 3, "max": 6},
                "requiredSections": ["Abstract", "Introduction", "Conclusion"],
            },
            "citation": {"style": "IEEE"},
            "layout": {"columns": "double"},
        },
    )
    user2_j1 = GuidelineRule(
        owner_user_id=u2.user_id,
        journal_id=j1.journal_id,
        name="User 2 Private J1",
        origin="manual",
        version=5,
        is_active=True,
        rules={"general": {"maxWords": 12000}},
    )
    # j2: system seed rule only
    sys_j2 = GuidelineRule(
        owner_user_id=None,
        journal_id=j2.journal_id,
        name="System J2",
        origin="seed",
        version=1,
        is_active=True,
        rules={
            "general": {"maxWords": 10000, "keywords": {"min": 4, "max": 4}},
            "citation": {"style": "Harvard"},
            "layout": {"columns": "single"},
        },
    )
    # j3: only User 2 has a private rule; User 1 has NO rules
    user2_j3 = GuidelineRule(
        owner_user_id=u2.user_id,
        journal_id=j3.journal_id,
        name="User 2 J3",
        origin="manual",
        version=2,
        is_active=True,
        rules={"general": {"maxWords": 4000}},
    )
    db_session.add_all([sys_j1, user1_j1, user2_j1, sys_j2, user2_j3])
    db_session.flush()

    ids3 = f"{j1.journal_id},{j2.journal_id},{j3.journal_id}"
    res = client.get(f"/journals/compare?ids={ids3}&include=requirements", headers=h1)
    assert res.status_code == 200
    body = res.json()
    assert "requirements" in [g["key"] for g in body["groups"]]

    row_map = {r["key"]: r["values"] for r in body["rows"]}
    # JC-REQ-01, 02, 03, 04, 05
    assert [v["value"] for v in row_map["rulesSource"]] == ["My rules (v3)", "Built-in", None]
    assert [v["value"] for v in row_map["maxWords"]] == [6500, 10000, None]
    assert [v["value"] for v in row_map["maxAbstractWords"]] == [250, None, None]
    assert [v["value"] for v in row_map["citationStyle"]] == ["IEEE", "Harvard", None]
    assert [v["value"] for v in row_map["columns"]] == ["double", "single", None]
    assert [v["value"] for v in row_map["requiredSections"]] == [
        ["Abstract", "Introduction", "Conclusion"],
        None,
        None,
    ]
    assert [v["value"] for v in row_map["keywords"]] == ["3 to 6", "4", None]

    # JC-REQ-06: Batch resolution executes in a single SQL query
    sql_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal sql_count
        if statement.lstrip().upper().startswith("SELECT"):
            sql_count += 1

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _count_queries)
    try:
        resolved = resolve_effective_rules_for_journals(
            db_session, u1.user_id, [j1.journal_id, j2.journal_id, j3.journal_id]
        )
    finally:
        event.remove(engine, "before_cursor_execute", _count_queries)

    assert sql_count == 1
    assert resolved[j1.journal_id][1] == "user"
    assert resolved[j2.journal_id][1] == "system"
    assert j3.journal_id not in resolved

    # JC-REQ-07: Keywords range edge cases
    assert format_keywords_range({"min": 3, "max": 6}) == "3 to 6"
    assert format_keywords_range({"min": 5, "max": 5}) == "5"
    assert format_keywords_range({"min": 3}) == "At least 3"
    assert format_keywords_range({"max": 8}) == "Up to 8"
    assert format_keywords_range({}) is None


# =============================================================================
# 8.6 Catalog List & Alias Compatibility Tests
# =============================================================================


def test_jc_cat_01_to_06_catalog_list_and_aliases(client, users, cmp_journals):
    (_, headers), _ = users

    # JC-CAT-01: Default /journals response preserves JournalBrowseResponse
    r_def = client.get("/journals", headers=headers)
    assert r_def.status_code == 200
    d = r_def.json()
    for field in ("items", "total", "page", "limit", "totalPages", "categories", "publishers"):
        assert field in d

    # JC-CAT-02 & 03: search & subjectCategory alias
    r_cat = client.get("/journals?subjectCategory=Computer%20Vision&search=Alpha", headers=headers)
    assert r_cat.status_code == 200
    assert any(it["title"] == "Alpha Vision Journal" for it in r_cat.json()["items"])

    # JC-CAT-04: openAccess alias
    r_oa = client.get("/journals?openAccess=Subscription", headers=headers)
    assert r_oa.status_code == 200
    assert all(
        "subscription" in (it["openAccessType"] or "").lower()
        for it in r_oa.json()["items"]
    )

    # JC-CAT-05: pageSize & sort/order aliases
    r_page = client.get("/journals?page=1&pageSize=2&sort=citeScore&order=desc", headers=headers)
    assert r_page.status_code == 200
    dp = r_page.json()
    assert dp["limit"] == 2
    assert len(dp["items"]) == 2
    scores = [it["citeScore"] for it in dp["items"] if it["citeScore"] is not None]
    assert scores == sorted(scores, reverse=True)

    # Invalid sort returns 422
    assert client.get("/journals?sort=invalidCol", headers=headers).status_code == 422

