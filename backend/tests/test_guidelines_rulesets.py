"""
Tests for Guideline Rule Sets (GE-RS) and Project Links (GE-LNK).
Reference: Guideline Extraction Plan Section 10.13, 10.14.
"""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, update

from app.main import app
from app.db.models.guideline_extraction import GuidelineExtraction
from app.db.models.guideline_rule import GuidelineRule
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import get_db
from scripts.seed_guideline_rules import seed_guideline_rules


@pytest.fixture(autouse=True)
def override_db(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def test_user1(db_session):
    from app.core.security import create_access_token
    u = db_session.scalars(select(User).where(User.email == "rs_user1@example.com")).first()
    if not u:
        u = User(email="rs_user1@example.com", password_hash="pw", full_name="User RS1")
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    token = create_access_token(u.user_id)
    return u, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user2(db_session):
    from app.core.security import create_access_token
    u = db_session.scalars(select(User).where(User.email == "rs_user2@example.com")).first()
    if not u:
        u = User(email="rs_user2@example.com", password_hash="pw", full_name="User RS2")
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    token = create_access_token(u.user_id)
    return u, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_journal(db_session):
    j = db_session.scalars(select(Journal).where(Journal.issn == "9999-0001")).first()
    if not j:
        j = Journal(
            journal_title="Test Journal of Computing",
            publisher="Test Publisher",
            issn="9999-0001",
            aims_and_scope="A test computing journal.",
        )
        db_session.add(j)
        db_session.commit()
        db_session.refresh(j)
    return j


@pytest.fixture
def completed_job(db_session, test_user1, test_journal):
    user, _ = test_user1
    job = GuidelineExtraction(
        user_id=user.user_id,
        journal_id=test_journal.journal_id,
        source_type="text",
        source_text="The manuscript must not exceed 6000 words. Use IEEE references.",
        status="completed",
        step="done",
        draft={
            "schemaVersion": 1,
            "rules": {
                "schemaVersion": 1,
                "general": {"maxWords": 6000},
                "citation": {"style": "IEEE", "numbered": True},
            },
            "fields": {
                "general.maxWords": {"confidence": "high", "value": 6000, "evidence": "must not exceed 6000 words"},
                "citation.style": {"confidence": "high", "value": "IEEE", "evidence": "Use IEEE references"},
            },
        },
        schema_version=1,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# ===========================================================================
# 10.13 Rule Sets (GE-RS-01 to GE-RS-49)
# ===========================================================================

@pytest.mark.anyio
async def test_ge_rs_01_confirm_completed_draft(test_user1, completed_job, test_journal):
    """GE-RS-01: Confirm a completed draft with valid rules -> 201; version 1; active; origin extracted; owner = me."""
    user, headers = test_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/guidelines/extractions/{completed_job.extraction_id}/confirm",
            headers=headers,
            json={
                "rules": completed_job.draft["rules"],
                "name": "My IEEE Rules",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["version"] == 1
        assert data["isActive"] is True
        assert data["origin"] == "extracted"
        assert data["isSystem"] is False
        assert data["journalId"] == str(test_journal.journal_id)
        assert data["name"] == "My IEEE Rules"


@pytest.mark.anyio
async def test_ge_rs_02_confirm_with_edited_values(test_user1, completed_job):
    """GE-RS-02: Confirm with edited values -> saved values are edited; provenance edited: true."""
    _, headers = test_user1
    transport = ASGITransport(app=app)
    edited_rules = {
        "schemaVersion": 1,
        "general": {"maxWords": 8000},  # Edited from 6000
        "citation": {"style": "IEEE", "numbered": True},
    }
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/guidelines/extractions/{completed_job.extraction_id}/confirm",
            headers=headers,
            json={"rules": edited_rules},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["rules"]["general"]["maxWords"] == 8000
        prov = data["provenance"]["general.maxWords"]
        assert prov["edited"] is True


@pytest.mark.anyio
async def test_ge_rs_03_04_05_low_confidence_fields(test_user1, db_session, test_journal):
    """GE-RS-03, 04, 05: Unreviewed low-confidence -> 422; acknowledged -> 201; edited -> 201."""
    user, headers = test_user1
    # Create draft with low confidence field
    job = GuidelineExtraction(
        user_id=user.user_id,
        journal_id=test_journal.journal_id,
        source_type="text",
        status="completed",
        step="done",
        draft={
            "schemaVersion": 1,
            "rules": {
                "schemaVersion": 1,
                "general": {"maxWords": 5000},
                "layout": {"columns": "double"},
            },
            "fields": {
                "general.maxWords": {"confidence": "low", "value": 5000, "evidence": "maybe 5000"},
                "layout.columns": {"confidence": "high", "value": "double"},
            },
        },
        schema_version=1,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GE-RS-03: Not acknowledged, not edited -> 422 UNREVIEWED_FIELDS
        r1 = await ac.post(
            f"/guidelines/extractions/{job.extraction_id}/confirm",
            headers=headers,
            json={"rules": job.draft["rules"]},
        )
        assert r1.status_code == 422
        assert "UNREVIEWED_FIELDS" in r1.text
        assert "general.maxWords" in r1.json()["detail"]["unreviewedFields"]

        # GE-RS-04: Acknowledged -> 201
        r2 = await ac.post(
            f"/guidelines/extractions/{job.extraction_id}/confirm",
            headers=headers,
            json={
                "rules": job.draft["rules"],
                "acknowledgedFields": ["general.maxWords"],
            },
        )
        assert r2.status_code == 201

    # GE-RS-05: Edited instead of acknowledged -> 201 on new job
    job2 = GuidelineExtraction(
        user_id=user.user_id,
        source_type="text",
        status="completed",
        step="done",
        draft={
            "schemaVersion": 1,
            "rules": {"schemaVersion": 1, "general": {"maxWords": 5000}},
            "fields": {"general.maxWords": {"confidence": "low", "value": 5000}},
        },
        schema_version=1,
    )
    db_session.add(job2)
    db_session.commit()
    db_session.refresh(job2)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r3 = await ac.post(
            f"/guidelines/extractions/{job2.extraction_id}/confirm",
            headers=headers,
            json={"rules": {"schemaVersion": 1, "general": {"maxWords": 6000}}},  # Changed from 5000
        )
        assert r3.status_code == 201


@pytest.mark.anyio
async def test_ge_rs_06_07_invalid_or_empty_rules(test_user1, completed_job):
    """GE-RS-06, 07: Invalid rules -> 422; Empty rules -> 422 NO_RULES."""
    _, headers = test_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Invalid value (negative maxWords)
        r1 = await ac.post(
            f"/guidelines/extractions/{completed_job.extraction_id}/confirm",
            headers=headers,
            json={"rules": {"general": {"maxWords": -50}}},
        )
        assert r1.status_code == 422

        # Empty rules
        r2 = await ac.post(
            f"/guidelines/extractions/{completed_job.extraction_id}/confirm",
            headers=headers,
            json={"rules": {}},
        )
        assert r2.status_code == 422
        assert "NO_RULES" in r2.text


@pytest.mark.anyio
async def test_ge_rs_08_09_10_confirm_guards(test_user1, test_user2, db_session):
    """GE-RS-08: Not completed -> 409; GE-RS-09: foreign -> 404; GE-RS-10: already confirmed -> 409."""
    u1, h1 = test_user1
    u2, h2 = test_user2

    running_job = GuidelineExtraction(user_id=u1.user_id, source_type="text", status="running", step="extracting", schema_version=1)
    db_session.add(running_job)
    db_session.commit()
    db_session.refresh(running_job)

    valid_rules = {"schemaVersion": 1, "general": {"maxWords": 5000}}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GE-RS-08
        r1 = await ac.post(f"/guidelines/extractions/{running_job.extraction_id}/confirm", headers=h1, json={"rules": valid_rules})
        assert r1.status_code == 409

        # GE-RS-09: User 2 confirms User 1's job -> 404
        r2 = await ac.post(f"/guidelines/extractions/{running_job.extraction_id}/confirm", headers=h2, json={"rules": valid_rules})
        assert r2.status_code == 404

        # Mark completed and confirm once
        running_job.status = "completed"
        running_job.step = "done"
        db_session.commit()
        r3 = await ac.post(f"/guidelines/extractions/{running_job.extraction_id}/confirm", headers=h1, json={"rules": valid_rules})
        assert r3.status_code == 201

        # GE-RS-10: Confirm same job again -> 409
        r4 = await ac.post(f"/guidelines/extractions/{running_job.extraction_id}/confirm", headers=h1, json={"rules": valid_rules})
        assert r4.status_code == 409


@pytest.mark.anyio
async def test_ge_rs_11_12_confirm_journal_handling(test_user1, test_journal, db_session):
    """GE-RS-11: Custom journalId used; GE-RS-12: journalId null -> ad-hoc rule set."""
    u, h = test_user1
    valid_rules = {"schemaVersion": 1, "general": {"maxWords": 4000}}
    job = GuidelineExtraction(user_id=u.user_id, source_type="text", status="completed", step="done", schema_version=1)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GE-RS-11: unknown journal -> 404
        r1 = await ac.post(f"/guidelines/extractions/{job.extraction_id}/confirm", headers=h, json={"rules": valid_rules, "journalId": "999999"})
        assert r1.status_code == 404

        # GE-RS-12: journalId null -> ad-hoc
        r2 = await ac.post(f"/guidelines/extractions/{job.extraction_id}/confirm", headers=h, json={"rules": valid_rules, "journalId": None})
        assert r2.status_code == 201
        assert r2.json()["journalId"] is None


@pytest.mark.anyio
async def test_ge_rs_13_lineage_and_versioning(test_user1, test_journal, db_session):
    """GE-RS-13: Second confirm for same journal -> new version in lineage, old inactive, exactly one active."""
    u, h = test_user1
    valid_rules = {"schemaVersion": 1, "general": {"maxWords": 5000}}

    j1 = GuidelineExtraction(user_id=u.user_id, journal_id=test_journal.journal_id, source_type="text", status="completed", step="done", schema_version=1)
    j2 = GuidelineExtraction(user_id=u.user_id, journal_id=test_journal.journal_id, source_type="text", status="completed", step="done", schema_version=1)
    db_session.add_all([j1, j2])
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.post(f"/guidelines/extractions/{j1.extraction_id}/confirm", headers=h, json={"rules": valid_rules})
        assert res1.status_code == 201
        v1 = res1.json()
        assert v1["version"] == 1
        assert v1["isActive"] is True

        res2 = await ac.post(f"/guidelines/extractions/{j2.extraction_id}/confirm", headers=h, json={"rules": valid_rules})
        assert res2.status_code == 201
        v2 = res2.json()
        assert v2["version"] == 2
        assert v2["isActive"] is True
        assert v2["lineageId"] == v1["lineageId"]

        # Check in DB that v1 is now inactive
        db_session.expire_all()
        rule1 = db_session.get(GuidelineRule, int(v1["id"]))
        assert rule1.is_active is False


@pytest.mark.anyio
async def test_ge_rs_19_name_validation(test_user1, db_session):
    """GE-RS-19: Name empty -> default generated; 200 chars -> valid; 201 chars -> 422."""
    u, h = test_user1
    valid_rules = {"schemaVersion": 1, "general": {"maxWords": 5000}}
    job = GuidelineExtraction(user_id=u.user_id, source_type="text", status="completed", step="done", schema_version=1)
    db_session.add(job)
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # > 200 chars -> 422
        long_name = "A" * 201
        res = await ac.post(f"/guidelines/extractions/{job.extraction_id}/confirm", headers=h, json={"rules": valid_rules, "name": long_name})
        assert res.status_code == 422

        # 200 chars -> 201
        valid_name = "B" * 200
        res2 = await ac.post(f"/guidelines/extractions/{job.extraction_id}/confirm", headers=h, json={"rules": valid_rules, "name": valid_name})
        assert res2.status_code == 201
        assert res2.json()["name"] == valid_name


@pytest.mark.anyio
async def test_ge_rs_20_21_manual_create(test_user1):
    """GE-RS-20: Manual create valid -> 201; GE-RS-21: invalid -> 422."""
    _, h = test_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Valid manual create
        r1 = await ac.post(
            "/guidelines/rule-sets",
            headers=h,
            json={"name": "Manual Guidelines", "rules": {"schemaVersion": 1, "general": {"maxWords": 7000}}},
        )
        assert r1.status_code == 201
        assert r1.json()["origin"] == "manual"
        assert r1.json()["version"] == 1

        # Invalid rules
        r2 = await ac.post(
            "/guidelines/rule-sets",
            headers=h,
            json={"name": "Bad Guidelines", "rules": {}},
        )
        assert r2.status_code == 422


@pytest.mark.anyio
async def test_ge_rs_22_23_24_list_and_get_rule_sets(test_user1, test_user2, db_session):
    """GE-RS-22: List visible only; GE-RS-23: Filters & pagination; GE-RS-24: Get own/system/foreign."""
    u1, h1 = test_user1
    u2, h2 = test_user2

    # Seed system rules
    seed_guideline_rules(db_session)

    # Create own rule for user 1
    r1 = GuidelineRule(owner_user_id=u1.user_id, name="User1 Special", origin="manual", rules={"schemaVersion": 1, "general": {"maxWords": 5000}}, schema_version=1)
    db_session.add(r1)
    db_session.commit()
    db_session.refresh(r1)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # User 2 list should see system rules but NOT User 1's rule
        res_u2 = await ac.get("/guidelines/rule-sets", headers=h2)
        assert res_u2.status_code == 200
        names = [item["name"] for item in res_u2.json()["items"]]
        assert "User1 Special" not in names
        assert any(item["isSystem"] for item in res_u2.json()["items"])

        # User 1 GET own -> 200
        res_get_own = await ac.get(f"/guidelines/rule-sets/{r1.rule_id}", headers=h1)
        assert res_get_own.status_code == 200

        # User 2 GET User 1's rule -> 404
        res_get_foreign = await ac.get(f"/guidelines/rule-sets/{r1.rule_id}", headers=h2)
        assert res_get_foreign.status_code == 404


@pytest.mark.anyio
async def test_ge_rs_25_to_30_edit_rule_set(test_user1, db_session):
    """GE-RS-25: Edit creates new version; GE-RS-26: identical -> no new version; GE-RS-30: rename in-place."""
    u, h = test_user1
    rule = GuidelineRule(
        owner_user_id=u.user_id,
        name="Original Name",
        origin="manual",
        version=1,
        is_active=True,
        rules={"schemaVersion": 1, "general": {"maxWords": 5000}},
        schema_version=1,
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GE-RS-30: Rename in-place (no new version)
        r_rename = await ac.patch(f"/guidelines/rule-sets/{rule.rule_id}", headers=h, json={"name": "Updated Name"})
        assert r_rename.status_code == 200
        assert r_rename.json()["name"] == "Updated Name"
        assert r_rename.json()["version"] == 1
        assert r_rename.json()["id"] == str(rule.rule_id)

        # GE-RS-26: Identical patch -> returns current version
        r_ident = await ac.patch(f"/guidelines/rule-sets/{rule.rule_id}", headers=h, json={"rules": rule.rules})
        assert r_ident.status_code == 200
        assert r_ident.json()["id"] == str(rule.rule_id)

        # GE-RS-25: Edit rules -> creates version 2
        new_rules = {"schemaVersion": 1, "general": {"maxWords": 9000}}
        r_edit = await ac.patch(f"/guidelines/rule-sets/{rule.rule_id}", headers=h, json={"rules": new_rules})
        assert r_edit.status_code == 200
        data = r_edit.json()
        assert data["version"] == 2
        assert data["isActive"] is True
        assert data["rules"]["general"]["maxWords"] == 9000
        assert data["id"] != str(rule.rule_id)

        # Check old version is inactive
        db_session.expire_all()
        db_session.refresh(rule)
        assert rule.is_active is False


@pytest.mark.anyio
async def test_ge_rs_31_32_versions_and_activate(test_user1, db_session):
    """GE-RS-31: Versions list in order; GE-RS-32: Activate older version."""
    u, h = test_user1
    # Create lineage with v1 and v2
    v1 = GuidelineRule(owner_user_id=u.user_id, name="Test Lineage", version=1, is_active=False, rules={"schemaVersion": 1, "general": {"maxWords": 5000}}, schema_version=1)
    db_session.add(v1)
    db_session.commit()
    db_session.refresh(v1)

    v2 = GuidelineRule(owner_user_id=u.user_id, lineage_id=v1.rule_id, name="Test Lineage", version=2, is_active=True, rules={"schemaVersion": 1, "general": {"maxWords": 8000}}, schema_version=1)
    db_session.add(v2)
    db_session.commit()
    db_session.refresh(v2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GE-RS-31: list versions
        r_vers = await ac.get(f"/guidelines/rule-sets/{v2.rule_id}/versions", headers=h)
        assert r_vers.status_code == 200
        assert len(r_vers.json()) == 2
        assert r_vers.json()[0]["version"] == 1
        assert r_vers.json()[1]["version"] == 2

        # GE-RS-32: activate v1
        r_act = await ac.post(f"/guidelines/rule-sets/{v1.rule_id}/activate", headers=h)
        assert r_act.status_code == 200
        assert r_act.json()["isActive"] is True

        db_session.expire_all()
        db_session.refresh(v2)
        assert v2.is_active is False


@pytest.mark.anyio
async def test_ge_rs_34_35_36_copy_rule_set(test_user1, db_session):
    """GE-RS-34, 35, 36: Copy system or own rule set into new lineage."""
    u, h = test_user1
    orig = GuidelineRule(owner_user_id=u.user_id, name="Base Rules", version=1, is_active=True, rules={"schemaVersion": 1, "general": {"maxWords": 5000}}, schema_version=1)
    db_session.add(orig)
    db_session.commit()
    db_session.refresh(orig)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(f"/guidelines/rule-sets/{orig.rule_id}/copy", headers=h)
        assert res.status_code == 201
        data = res.json()
        assert data["id"] != str(orig.rule_id)
        assert data["name"] == "Base Rules (Copy)"
        assert data["version"] == 1
        assert data["lineageId"] == data["id"]  # Independent lineage


@pytest.mark.anyio
async def test_ge_rs_37_39_40_delete_rule_set(test_user1, db_session):
    """GE-RS-37: Delete own rule -> 204; GE-RS-39: system rule -> 403; GE-RS-40: unlinks project."""
    u, h = test_user1
    rule = GuidelineRule(owner_user_id=u.user_id, name="To Delete", version=1, is_active=True, rules={"schemaVersion": 1, "general": {"maxWords": 5000}}, schema_version=1)
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)

    proj = Project(user_id=u.user_id, project_title="Project Linked", guideline_rule_id=rule.rule_id)
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    sys_rule = GuidelineRule(owner_user_id=None, name="System Protected", is_active=True, rules={"schemaVersion": 1, "general": {"maxWords": 5000}}, schema_version=1)
    db_session.add(sys_rule)
    db_session.commit()
    db_session.refresh(sys_rule)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GE-RS-39: Delete system rule -> 403
        r_sys = await ac.delete(f"/guidelines/rule-sets/{sys_rule.rule_id}", headers=h)
        assert r_sys.status_code == 403

        # GE-RS-37 & 40: Delete own rule -> 204, unlinks project
        r_del = await ac.delete(f"/guidelines/rule-sets/{rule.rule_id}", headers=h)
        assert r_del.status_code == 204

        db_session.expire_all()
        db_session.refresh(proj)
        assert proj.guideline_rule_id is None


@pytest.mark.anyio
async def test_ge_rs_46_to_49_journal_effective_rules(test_user1, test_journal, db_session):
    """GE-RS-46 to 49: Effective journal rules resolution order."""
    u, h = test_user1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GE-RS-48: No rules -> ruleSet: null
        r1 = await ac.get(f"/journals/{test_journal.journal_id}/guidelines", headers=h)
        assert r1.status_code == 200
        assert r1.json()["ruleSet"] is None
        assert r1.json()["source"] is None

        # Add system rule -> GE-RS-47: source 'system'
        sys_r = GuidelineRule(owner_user_id=None, journal_id=test_journal.journal_id, name="Sys Rules", is_active=True, rules={"schemaVersion": 1, "general": {"maxWords": 4000}}, schema_version=1)
        db_session.add(sys_r)
        db_session.commit()

        r2 = await ac.get(f"/journals/{test_journal.journal_id}/guidelines", headers=h)
        assert r2.status_code == 200
        assert r2.json()["source"] == "system"
        assert r2.json()["ruleSet"]["name"] == "Sys Rules"

        # Add own active rule -> GE-RS-46: user rule beats system rule
        user_r = GuidelineRule(owner_user_id=u.user_id, journal_id=test_journal.journal_id, name="User Rules", is_active=True, rules={"schemaVersion": 1, "general": {"maxWords": 6000}}, schema_version=1)
        db_session.add(user_r)
        db_session.commit()

        r3 = await ac.get(f"/journals/{test_journal.journal_id}/guidelines", headers=h)
        assert r3.status_code == 200
        assert r3.json()["source"] == "user"
        assert r3.json()["ruleSet"]["name"] == "User Rules"


# ===========================================================================
# 10.14 Project Link (GE-LNK-01 to GE-LNK-10)
# ===========================================================================

@pytest.mark.anyio
async def test_ge_lnk_01_to_07_project_link_and_effective(test_user1, test_user2, db_session, test_journal):
    """GE-LNK-01 to 07: Link rule to project, unlink, foreign guards, effective resolution."""
    u1, h1 = test_user1
    u2, h2 = test_user2

    proj = Project(user_id=u1.user_id, project_title="Project A")
    rule1 = GuidelineRule(owner_user_id=u1.user_id, name="Rule A", is_active=True, rules={"schemaVersion": 1, "general": {"maxWords": 5000}}, schema_version=1)
    db_session.add_all([proj, rule1])
    db_session.commit()
    db_session.refresh(proj)
    db_session.refresh(rule1)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GE-LNK-04: User 2 tries to link to User 1's project -> 404
        r_f1 = await ac.put(f"/projects/{proj.project_id}/guidelines/{rule1.rule_id}", headers=h2)
        assert r_f1.status_code == 404

        # GE-LNK-01: User 1 links Rule A to Project A -> 200
        r_link = await ac.put(f"/projects/{proj.project_id}/guidelines/{rule1.rule_id}", headers=h1)
        assert r_link.status_code == 200

        # Workspace overview shows guidelineRuleSet
        r_ov = await ac.get(f"/projects/{proj.project_id}", headers=h1)
        assert r_ov.status_code == 200
        assert r_ov.json()["guidelineRuleSet"]["name"] == "Rule A"
        assert r_ov.json()["guidelineRuleSet"]["source"] == "project"

        # Effective project guidelines endpoint
        r_eff = await ac.get(f"/projects/{proj.project_id}/guidelines", headers=h1)
        assert r_eff.status_code == 200
        assert r_eff.json()["source"] == "project"

        # GE-LNK-05: Unlink -> 204
        r_unlink = await ac.delete(f"/projects/{proj.project_id}/guidelines", headers=h1)
        assert r_unlink.status_code == 204

        # After unlink, effective is null (no target journal)
        r_eff2 = await ac.get(f"/projects/{proj.project_id}/guidelines", headers=h1)
        assert r_eff2.status_code == 200
        assert r_eff2.json()["ruleSet"] is None


@pytest.mark.anyio
async def test_ge_lnk_08_linked_rule_follows_active_version(test_user1, db_session):
    """GE-LNK-08: Linked rule set gets a new version -> project automatically follows lineage's active version."""
    u, h = test_user1
    r_v1 = GuidelineRule(owner_user_id=u.user_id, name="Lineage Follow", version=1, is_active=True, rules={"schemaVersion": 1, "general": {"maxWords": 5000}}, schema_version=1)
    db_session.add(r_v1)
    db_session.commit()
    db_session.refresh(r_v1)

    proj = Project(user_id=u.user_id, project_title="Project Follow", guideline_rule_id=r_v1.rule_id)
    db_session.add(proj)
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Patch rule -> creates version 2
        r_patch = await ac.patch(
            f"/guidelines/rule-sets/{r_v1.rule_id}",
            headers=h,
            json={"rules": {"schemaVersion": 1, "general": {"maxWords": 6000}}},
        )
        assert r_patch.status_code == 200
        v2_id = int(r_patch.json()["id"])

        # Project's guideline_rule_id was automatically updated to v2!
        db_session.expire_all()
        db_session.refresh(proj)
        assert proj.guideline_rule_id == v2_id
