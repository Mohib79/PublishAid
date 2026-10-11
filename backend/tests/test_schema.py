import pytest
from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError, DataError, StatementError
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.journal import Journal
from app.db.models.project_journal import ProjectJournal
from app.db.models.guideline_rule import GuidelineRule
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
        role="researcher",
    )
    db_session.add(u1)
    db_session.flush()

    u2 = User(
        full_name="User Two",
        email="author@domain.com",
        password_hash="hash2",
        role="researcher",
    )
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.flush()

def test_invalid_enum_role(db_session):
    user = User(
        full_name="Bad Role",
        email="badrole@domain.com",
        password_hash="hash",
        role="superuser",  # not in ('researcher', 'admin')
    )
    db_session.add(user)
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()

def test_duplicate_project_journal(db_session):
    user = User(full_name="U", email="u_pj@domain.com", password_hash="h", role="researcher")
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
    user = User(full_name="U", email="u_sel@domain.com", password_hash="h", role="researcher")
    db_session.add(user)
    db_session.flush()

    project = Project(user_id=user.user_id, project_title="Proj Sel")
    j1 = Journal(journal_title="J Sel 1", publisher="P", aims_and_scope="Scope 1")
    j2 = Journal(journal_title="J Sel 2", publisher="P", aims_and_scope="Scope 2")
    db_session.add_all([project, j1, j2])
    db_session.flush()

    pj1 = ProjectJournal(project_id=project.project_id, journal_id=j1.journal_id, is_selected=True)
    db_session.add(pj1)
    db_session.flush()

    pj2 = ProjectJournal(project_id=project.project_id, journal_id=j2.journal_id, is_selected=True)
    db_session.add(pj2)
    with pytest.raises(IntegrityError):
        db_session.flush()

def test_user_delete_cascade(db_session):
    user = User(full_name="Cascade User", email="cascade@test.com", password_hash="h", role="researcher")
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
    user = User(full_name="U", email="restr@test.com", password_hash="h", role="researcher")
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
    user = User(full_name="U", email="setnull@test.com", password_hash="h", role="researcher")
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
