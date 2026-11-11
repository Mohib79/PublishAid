import pytest
from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError, DataError, StatementError
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.journal import Journal
from app.db.models.project_journal import ProjectJournal
from app.db.models.guideline_rule import GuidelineRule
from app.db.models.guideline_extraction import GuidelineExtraction
from app.db.models.template import Template
from app.db.models.conversion_job import ConversionJob
from app.db.models.compliance_report import ComplianceReport
from app.db.models.compliance_issue import ComplianceIssue


def test_tables_and_extension_exist(db_session, test_engine):
    inspector = inspect(test_engine)
    tables = set(inspector.get_table_names())
    expected_tables = {
        "users",
        "projects",
        "journals",
        "project_journals",
        "guideline_rules",
        "templates",
        "conversion_jobs",
        "compliance_reports",
        "compliance_issues",
        "activity_logs",
        "guideline_extractions",
        "alembic_version",
    }
    assert expected_tables.issubset(tables)

    ext = db_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
    ).scalar()
    assert ext == "vector"


def test_email_case_insensitive_uniqueness(db_session):
    u1 = User(
        full_name="User One",
        email="Author@Domain.com",
        password_hash="hash1",
    )
    db_session.add(u1)
    db_session.flush()

    u2 = User(
        full_name="User Two",
        email="author@domain.com",
        password_hash="hash2",
    )
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_enum_quartile(db_session):
    journal = Journal(
        journal_title="Invalid Quartile Journal",
        publisher="Pub",
        aims_and_scope="Scope description",
        quartile="Q5",  # Allowed: Q1, Q2, Q3, Q4
    )
    db_session.add(journal)
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()


def test_duplicate_project_journal(db_session):
    user = User(full_name="U", email="u_pj@domain.com", password_hash="h")
    db_session.add(user)
    db_session.flush()

    project = Project(user_id=user.user_id, project_title="P1")
    journal = Journal(
        journal_title="J1",
        publisher="Pub1",
        aims_and_scope="Scope text for J1",
    )
    db_session.add_all([project, journal])
    db_session.flush()

    pj1 = ProjectJournal(project_id=project.project_id, journal_id=journal.journal_id)
    db_session.add(pj1)
    db_session.flush()

    pj2 = ProjectJournal(project_id=project.project_id, journal_id=journal.journal_id)
    db_session.add(pj2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_multiple_selected_journals_blocked(db_session):
    user = User(full_name="U", email="u_sel@domain.com", password_hash="h")
    db_session.add(user)
    db_session.flush()

    project = Project(user_id=user.user_id, project_title="Proj Sel")
    j1 = Journal(journal_title="J Sel 1", publisher="P", aims_and_scope="Scope 1")
    j2 = Journal(journal_title="J Sel 2", publisher="P", aims_and_scope="Scope 2")
    db_session.add_all([project, j1, j2])
    db_session.flush()

    pj1 = ProjectJournal(project_id=project.project_id, journal_id=j1.journal_id, is_selected=True, is_shortlisted=True)
    db_session.add(pj1)
    db_session.flush()

    pj2 = ProjectJournal(project_id=project.project_id, journal_id=j2.journal_id, is_selected=True, is_shortlisted=True)
    db_session.add(pj2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_user_delete_cascade(db_session):
    user = User(full_name="Cascade User", email="cascade@test.com", password_hash="h")
    db_session.add(user)
    db_session.flush()

    project = Project(user_id=user.user_id, project_title="Cascade Proj")
    journal = Journal(journal_title="J Cascade", publisher="Pub", aims_and_scope="Scope")
    db_session.add_all([project, journal])
    db_session.flush()

    pj = ProjectJournal(project_id=project.project_id, journal_id=journal.journal_id)
    job = ConversionJob(project_id=project.project_id, conversion_type="format_conversion")
    report = ComplianceReport(project_id=project.project_id, overall_status="passed")
    db_session.add_all([pj, job, report])
    db_session.flush()

    issue = ComplianceIssue(
        report_id=report.report_id,
        rule_type="max_word_count",
        severity="error",
        message="Too long",
    )
    db_session.add(issue)
    db_session.flush()

    proj_id = project.project_id
    job_id = job.job_id
    rep_id = report.report_id
    iss_id = issue.issue_id

    # Delete user
    db_session.delete(user)
    db_session.flush()
    db_session.expunge_all()

    # Check that project, job, report, issue are deleted in DB
    assert db_session.get(Project, proj_id) is None
    assert db_session.get(ConversionJob, job_id) is None
    assert db_session.get(ComplianceReport, rep_id) is None
    assert db_session.get(ComplianceIssue, iss_id) is None


def test_journal_delete_restricted_on_project_journal(db_session):
    user = User(full_name="U", email="restr@test.com", password_hash="h")
    db_session.add(user)
    db_session.flush()

    project = Project(user_id=user.user_id, project_title="Restr Proj")
    journal = Journal(journal_title="Restr J", publisher="P", aims_and_scope="Scope")
    db_session.add_all([project, journal])
    db_session.flush()

    pj = ProjectJournal(project_id=project.project_id, journal_id=journal.journal_id)
    db_session.add(pj)
    db_session.flush()

    db_session.delete(journal)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_journal_delete_set_null_and_cascade(db_session):
    user = User(full_name="U", email="setnull@test.com", password_hash="h")
    db_session.add(user)
    db_session.flush()

    project = Project(user_id=user.user_id, project_title="SetNull Proj")
    journal = Journal(journal_title="J SetNull", publisher="P", aims_and_scope="Scope")
    db_session.add_all([project, journal])
    db_session.flush()

    rule = GuidelineRule(journal_id=journal.journal_id, rules={"max_word_count": 5000})
    db_session.add(rule)
    db_session.flush()

    template = Template(
        journal_id=journal.journal_id,
        template_format="latex",
        template_file_path="/templates/sample.tex",
    )
    job = ConversionJob(
        project_id=project.project_id,
        conversion_type="format_conversion",
        source_journal_id=journal.journal_id,
    )
    db_session.add_all([template, job])
    db_session.flush()

    tmpl_id = template.template_id
    rule_id = rule.rule_id
    job_id = job.job_id

    # Delete journal
    db_session.delete(journal)
    db_session.flush()
    db_session.expunge_all()

    # Templates has ON DELETE CASCADE
    assert db_session.get(Template, tmpl_id) is None
    # GuidelineRule has ON DELETE SET NULL
    assert db_session.get(GuidelineRule, rule_id).journal_id is None
    # ConversionJob has ON DELETE SET NULL
    assert db_session.get(ConversionJob, job_id).source_journal_id is None


def test_guideline_rules_json_object_check(db_session):
    # Valid JSON object works
    valid_rule = GuidelineRule(rules={"max_words": 5000})
    db_session.add(valid_rule)
    db_session.flush()
    assert valid_rule.rule_id is not None

    # Invalid JSON array rejected by CHECK constraint
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("INSERT INTO guideline_rules (rules) VALUES ('[1, 2, 3]'::jsonb);")
        )
        db_session.flush()


def test_vector_roundtrip_and_dimension(db_session):
    vector_768 = [0.01 * (i % 10) for i in range(768)]
    journal = Journal(
        journal_title="Vector Journal",
        publisher="VecPub",
        aims_and_scope="Aims & Scope text",
        embedding=vector_768,
    )
    db_session.add(journal)
    db_session.flush()

    db_session.refresh(journal)
    assert len(journal.embedding) == 768

    # Wrong dimension (e.g. 10 dimensions instead of 768) should be rejected
    with pytest.raises((DataError, StatementError, IntegrityError)):
        bad_j = Journal(
            journal_title="Bad Vec",
            publisher="P",
            aims_and_scope="S",
            embedding=[0.1, 0.2, 0.3],
        )
        db_session.add(bad_j)
        db_session.flush()


def test_numeric_check_constraints(db_session):
    with pytest.raises(IntegrityError):
        bad_rate = Journal(
            journal_title="Bad Rate",
            publisher="P",
            aims_and_scope="Scope",
            acceptance_rate=150.0,
        )
        db_session.add(bad_rate)
        db_session.flush()

    db_session.rollback()

    with pytest.raises(IntegrityError):
        bad_weeks = Journal(
            journal_title="Bad Weeks",
            publisher="P",
            aims_and_scope="Scope",
            review_weeks=-1,
        )
        db_session.add(bad_weeks)
        db_session.flush()


def test_project_keywords_array(db_session):
    user = User(full_name="KW User", email="kw_user@domain.com", password_hash="h")
    db_session.add(user)
    db_session.flush()

    # Default empty keywords
    p1 = Project(user_id=user.user_id, project_title="Project Default KW")
    db_session.add(p1)
    db_session.flush()
    db_session.refresh(p1)
    assert p1.keywords == []

    # Project with explicit keywords
    p2 = Project(
        user_id=user.user_id,
        project_title="Project With KW",
        keywords=["neural networks", "computer vision", "deep learning"],
    )
    db_session.add(p2)
    db_session.flush()
    db_session.refresh(p2)
    assert p2.keywords == ["neural networks", "computer vision", "deep learning"]


def test_project_journal_is_shortlisted(db_session):
    user = User(full_name="Shortlist User", email="sl_user@domain.com", password_hash="h")
    db_session.add(user)
    db_session.flush()

    project = Project(user_id=user.user_id, project_title="Shortlist Test Project")
    journal = Journal(journal_title="Shortlist Target Journal", publisher="P", aims_and_scope="Scope")
    db_session.add_all([project, journal])
    db_session.flush()

    pj = ProjectJournal(project_id=project.project_id, journal_id=journal.journal_id)
    db_session.add(pj)
    db_session.flush()
    db_session.refresh(pj)
    assert pj.is_shortlisted is False

    pj.is_shortlisted = True
    db_session.flush()
    db_session.refresh(pj)
    assert pj.is_shortlisted is True


def test_ge_db_02_guideline_rules_defaults(db_session):
    rule = GuidelineRule(rules={"max_words": 8000})
    db_session.add(rule)
    db_session.flush()
    db_session.refresh(rule)
    assert rule.name == "Default Rules"
    assert rule.origin == "seed"
    assert rule.schema_version == 1
    assert rule.provenance == {}
    assert rule.owner_user_id is None
    assert rule.lineage_id is None
    assert rule.is_active is True


def test_ge_db_05_active_version_per_lineage_partial_unique(db_session):
    r1 = GuidelineRule(rules={"v": 1}, is_active=True)
    db_session.add(r1)
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            r2 = GuidelineRule(lineage_id=r1.rule_id, rules={"v": 2}, is_active=True)
            db_session.add(r2)
            db_session.flush()


def test_ge_db_06_to_09_active_rules_owner_journal_constraints(db_session):
    u1 = User(full_name="U1", email="u1_gr@test.com", password_hash="h")
    u2 = User(full_name="U2", email="u2_gr@test.com", password_hash="h")
    j1 = Journal(journal_title="J1", publisher="P", aims_and_scope="S")
    db_session.add_all([u1, u2, j1])
    db_session.flush()

    # GE-DB-08: System rule set active for j1
    sys_rule = GuidelineRule(owner_user_id=None, journal_id=j1.journal_id, is_active=True, rules={"scope": "system"})
    # GE-DB-07: User 1 active rule set for j1
    u1_rule = GuidelineRule(owner_user_id=u1.user_id, journal_id=j1.journal_id, is_active=True, rules={"scope": "u1"})
    # User 2 active rule set for j1
    u2_rule = GuidelineRule(owner_user_id=u2.user_id, journal_id=j1.journal_id, is_active=True, rules={"scope": "u2"})
    db_session.add_all([sys_rule, u1_rule, u2_rule])
    db_session.flush()

    # GE-DB-06: Second active rule set for same user and same journal rejected
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            u1_dup = GuidelineRule(owner_user_id=u1.user_id, journal_id=j1.journal_id, is_active=True, rules={"scope": "u1_dup"})
            db_session.add(u1_dup)
            db_session.flush()

    # GE-DB-09: Multiple active ad-hoc (no journal) rule sets for same user allowed
    adhoc1 = GuidelineRule(owner_user_id=u1.user_id, journal_id=None, is_active=True, rules={"adhoc": 1})
    adhoc2 = GuidelineRule(owner_user_id=u1.user_id, journal_id=None, is_active=True, rules={"adhoc": 2})
    db_session.add_all([adhoc1, adhoc2])
    db_session.flush()
    assert adhoc1.rule_id is not None
    assert adhoc2.rule_id is not None


def test_ge_db_10_extraction_checks_and_ge_db_16_token_counts(db_session):
    u = User(full_name="Extr User", email="extr_user@test.com", password_hash="h")
    db_session.add(u)
    db_session.flush()

    # Invalid source_type
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            e_bad = GuidelineExtraction(user_id=u.user_id, source_type="invalid")
            db_session.add(e_bad)
            db_session.flush()

    # Negative tokens (GE-DB-16)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            e_neg = GuidelineExtraction(user_id=u.user_id, source_type="text", input_tokens=-1)
            db_session.add(e_neg)
            db_session.flush()

    # Valid extraction
    e_valid = GuidelineExtraction(
        user_id=u.user_id,
        source_type="url",
        source_url="https://example.org/authors",
        status="queued",
        step="queued",
        warnings=[],
    )
    db_session.add(e_valid)
    db_session.flush()
    assert e_valid.extraction_id is not None


def test_ge_db_11_to_15_cascades_and_foreign_keys(db_session):
    u = User(full_name="Cascade GE", email="cascade_ge@test.com", password_hash="h")
    db_session.add(u)
    db_session.flush()

    j = Journal(journal_title="J Cascade GE", publisher="P", aims_and_scope="S")
    db_session.add(j)
    db_session.flush()

    r = GuidelineRule(owner_user_id=u.user_id, journal_id=j.journal_id, rules={"w": 5000})
    db_session.add(r)
    db_session.flush()

    p = Project(user_id=u.user_id, project_title="Project Linked GE", guideline_rule_id=r.rule_id)
    db_session.add(p)
    db_session.flush()

    e = GuidelineExtraction(
        user_id=u.user_id,
        journal_id=j.journal_id,
        project_id=p.project_id,
        source_type="text",
        confirmed_rule_id=r.rule_id,
    )
    tmpl = Template(journal_id=j.journal_id, rule_id=r.rule_id, template_format="latex", template_file_path="/t.tex")
    cjob = ConversionJob(project_id=p.project_id, conversion_type="format_conversion", target_guideline_id=r.rule_id)
    rep = ComplianceReport(project_id=p.project_id, rule_id=r.rule_id, overall_status="passed")
    db_session.add_all([e, tmpl, cjob, rep])
    db_session.flush()

    r_id = r.rule_id
    p_id = p.project_id
    e_id = e.extraction_id
    tmpl_id = tmpl.template_id
    cjob_id = cjob.job_id
    rep_id = rep.report_id

    # GE-DB-13, 14, 15: Delete rule set -> project.guideline_rule_id, extraction.confirmed_rule_id, template.rule_id, conversion_job.target_guideline_id, compliance_report.rule_id become NULL
    db_session.delete(r)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(Project, p_id).guideline_rule_id is None
    assert db_session.get(GuidelineExtraction, e_id).confirmed_rule_id is None
    assert db_session.get(Template, tmpl_id).rule_id is None
    assert db_session.get(ConversionJob, cjob_id).target_guideline_id is None
    assert db_session.get(ComplianceReport, rep_id).rule_id is None

    # GE-DB-12: Delete journal -> journal_id on rule sets and extractions becomes NULL
    r2 = GuidelineRule(owner_user_id=u.user_id, journal_id=j.journal_id, rules={"w": 6000})
    e2 = GuidelineExtraction(user_id=u.user_id, journal_id=j.journal_id, source_type="text")
    db_session.add_all([r2, e2])
    db_session.flush()
    r2_id = r2.rule_id
    e2_id = e2.extraction_id

    db_session.delete(j)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(GuidelineRule, r2_id).journal_id is None
    assert db_session.get(GuidelineExtraction, e2_id).journal_id is None

    # GE-DB-11: Delete user -> extractions and owned rule sets deleted (cascade)
    db_session.delete(db_session.get(User, u.user_id))
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(GuidelineRule, r2_id) is None
    assert db_session.get(GuidelineExtraction, e2_id) is None


def test_ge_db_17_indexes_exist(db_session, test_engine):
    inspector = inspect(test_engine)
    extr_indexes = {ix["name"] for ix in inspector.get_indexes("guideline_extractions")}
    expected_extr_ix = {
        "ix_guideline_extractions_user_created",
        "ix_guideline_extractions_user_status",
        "ix_guideline_extractions_user_hash",
    }
    assert expected_extr_ix.issubset(extr_indexes)

    rules_indexes = {ix["name"] for ix in inspector.get_indexes("guideline_rules")}
    assert "ix_guideline_rules_owner_journal_active" in rules_indexes
    assert "uq_guideline_rules_active_lineage" in rules_indexes
    assert "uq_guideline_rules_owner_journal_active" in rules_indexes


