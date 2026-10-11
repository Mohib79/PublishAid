# PublishAid — Database Implementation Plan

**Audience:** the AI coding agent (Antigravity) that will implement this plan, and the PublishAid team reviewing its work.
**Scope:** database layer only (PostgreSQL + pgvector, SQLAlchemy models, Alembic migrations, seed data, embeddings, verification).
**Out of scope:** REST endpoints, authentication logic, LLM/AI engines, document conversion, anything inside the frontend.

---

## 0. Hard Rules (read first, apply to every phase)

Paste this block at the top of every Antigravity session/task.

1. **Do NOT modify, create, rename, move or delete anything inside the `frontend/` folder.** The frontend is finished and must stay byte-for-byte identical. Do not run `npm install`, formatters, linters or generators there.
2. All new work goes in a **new top-level `backend/` folder** (sibling of `frontend/`). If a `backend/` folder already exists, inspect it first and extend it; never overwrite existing files without showing a diff.
3. Do not edit root-level files (root `.gitignore`, root `README.md`, `package.json`, etc.). Use `backend/.gitignore` and `backend/README.md` instead.
4. Never commit secrets. Only `backend/.env.example` is committed; `backend/.env` is git-ignored.
5. Every schema change goes through an **Alembic migration**. Never create or alter tables by hand or with `Base.metadata.create_all()` outside of tests.
6. Work **one phase at a time**. At the end of each phase, run that phase's verification steps and report results before continuing.
7. After the final phase, run `git status` and `git diff --stat -- frontend/` and confirm the frontend has **zero** changes.

---

## 1. Decisions Already Made (from the FYP report)

| Topic | Decision | Source in report |
|---|---|---|
| Database | PostgreSQL | 4.7.2, 4.9, 5.7.1 |
| Backend | Python 3.10+ with FastAPI | 4.7.2, 5.7.1 |
| Flexible data | Guideline rules stored as JSONB | 5.4.2, 5.7.1 |
| Semantic matching | Journal scope embeddings stored in DB (SPECTER, 768-dim) | 5.3.2.2, 4.7.2 |
| Privacy | Manuscript files are temporary and purged; DB keeps metadata only | 5.4.3 |
| Entities | 9 tables: User, Project, Journal, ProjectJournal, GuidelineRule, Template, ConversionJob, ComplianceReport, ComplianceIssue | 4.9 |

### Deliberate deviations from the report's data dictionary

These fix inconsistencies found in the report. Implement the fixed version and note it in `backend/README.md` so the report can be updated to match.

| # | Report says | Implement instead | Why |
|---|---|---|---|
| D1 | Journal has no embedding column | Add `embedding vector(768)` (nullable) + HNSW index | Section 5.3.2.2 says vectors are queried in the DB |
| D2 | GuidelineRule has fixed columns (`max_word_count`, `citation_style`, ...) | Keep `journal_id`, `source_url`, `updated_at`, add `rules JSONB`, `version`, `is_active`. Put the formatting rules inside `rules` | Section 5.4.2 requires rules decoupled from schema |
| D3 | ConversionJob `source_journal_id`, `target_journal_id`, `target_guideline_id` typed String | Use Integer FKs | They reference Integer primary keys |
| D4 | ConversionJob `conversion_type` is Integer (0/1) | String enum: `format_conversion`, `manuscript_transformation` | Self-documenting, no magic numbers |
| D5 | Project `current_file_path` always present | Keep nullable and add `file_deleted_at` | Files are purged after the session (5.4.3) |
| D6 | Status/role fields are free `String` | Constrain with CHECK constraints (enum-like) | Prevents invalid values |
| D7 | No uniqueness on ProjectJournal | Unique `(project_id, journal_id)` | A journal should be shortlisted once per project |

---

## 2. Target Folder Layout

Create exactly this (nothing outside `backend/`):

```
<repo-root>/
├── frontend/                  # DO NOT TOUCH
└── backend/
    ├── docker-compose.yml
    ├── .env.example
    ├── .gitignore
    ├── README.md
    ├── requirements.txt
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py
    │   ├── script.py.mako
    │   └── versions/
    ├── app/
    │   ├── __init__.py
    │   ├── core/
    │   │   ├── __init__.py
    │   │   └── config.py          # settings from env vars
    │   └── db/
    │       ├── __init__.py
    │       ├── base.py            # DeclarativeBase + naming convention
    │       ├── session.py         # engine, SessionLocal, get_db()
    │       └── models/
    │           ├── __init__.py    # imports every model (needed by Alembic)
    │           ├── user.py
    │           ├── project.py
    │           ├── journal.py
    │           ├── project_journal.py
    │           ├── guideline_rule.py
    │           ├── template.py
    │           ├── conversion_job.py
    │           ├── compliance_report.py
    │           └── compliance_issue.py
    ├── scripts/
    │   ├── check_db.py            # connectivity + extension check
    │   ├── seed_journals.py
    │   ├── seed_dev_data.py       # demo user/project for testing
    │   └── embed_journals.py
    ├── seed/
    │   └── journals.csv
    └── tests/
        ├── conftest.py
        └── test_schema.py
```

If the repo already has a backend folder with a different name, stop and ask which one to use rather than creating a duplicate.

---

## Phase 1 — Pre-flight Checks

**Goal:** confirm the environment and make sure the frontend is safe.

Tasks:
1. Run `git status` and record that the working tree state. Run `git log -1` for reference.
2. List the repo root and confirm `frontend/` exists. Do not open or edit files in it. (Reading `frontend/` to understand which fields the UI expects is allowed; see Phase 1b.)
3. Check installed tools and report versions: `python --version` (need 3.10+), `docker --version`, `docker compose version`, `git --version`.
4. If Docker is not installed, stop and tell the user. As a fallback, a local PostgreSQL 16 install with the `pgvector` extension also works, but Docker is strongly preferred so all three team members get an identical setup.

### Phase 1b (optional, read-only) — Align schema with the UI

Search `frontend/` **read-only** for the fields it displays or submits (journal cards: acceptance rate, review time, quartile; project forms: title, abstract; compliance results: pass/fail list). Report any field the UI uses that is **missing** from the schema in Section 5. Do not change the frontend; if there is a mismatch, propose a backend schema change instead and wait for approval.

**Verification:** `git status` unchanged; tool versions reported.

---

## Phase 2 — PostgreSQL + pgvector in Docker

**Goal:** a reproducible local database.

Create `backend/docker-compose.yml`:

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: publishaid_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-publishaid}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-publishaid_dev}
      POSTGRES_DB: ${POSTGRES_DB:-publishaid}
    ports:
      - "5432:5432"
    volumes:
      - publishaid_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-publishaid} -d ${POSTGRES_DB:-publishaid}"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  publishaid_pgdata:
```

Create `backend/.env.example` (and copy it to `backend/.env`):

```
POSTGRES_USER=publishaid
POSTGRES_PASSWORD=publishaid_dev
POSTGRES_DB=publishaid
DATABASE_URL=postgresql+psycopg://publishaid:publishaid_dev@localhost:5432/publishaid
TEST_DATABASE_URL=postgresql+psycopg://publishaid:publishaid_dev@localhost:5432/publishaid_test
```

Create `backend/.gitignore` containing at least: `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`.

If port 5432 is already in use on the machine, change the host side to `5433:5432` and update `DATABASE_URL` accordingly (tell the user).

**Verification:**
- `docker compose up -d` from `backend/` → container is `healthy`.
- `docker exec -it publishaid_db psql -U publishaid -d publishaid -c "SELECT version();"` works.
- Create the test DB: `docker exec -it publishaid_db psql -U publishaid -c "CREATE DATABASE publishaid_test;"`.

---

## Phase 3 — Python Environment & Dependencies

Create a virtualenv in `backend/.venv` and a `backend/requirements.txt`:

```
fastapi
uvicorn[standard]
sqlalchemy>=2.0
alembic
psycopg[binary]>=3.1
pgvector
pydantic-settings
python-dotenv
pytest
```

Embedding generation needs heavier packages; keep them in a **separate** file `backend/requirements-embeddings.txt` so the base install stays light:

```
sentence-transformers
torch
```

Pin exact versions with `pip freeze` after the first successful install, and record the versions in `README.md`.

**Verification:** `python -c "import sqlalchemy, alembic, psycopg, pgvector; print('ok')"`.

---

## Phase 4 — Configuration & Database Session

### `app/core/config.py`
Use `pydantic-settings` to load `DATABASE_URL` (and `TEST_DATABASE_URL`) from `backend/.env`. Fail loudly with a clear message if `DATABASE_URL` is missing.

### `app/db/base.py`
Use SQLAlchemy 2.0 typed style (`DeclarativeBase`, `Mapped`, `mapped_column`) and a **naming convention** so Alembic generates predictable constraint names:

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

### `app/db/session.py`
Create the engine (`pool_pre_ping=True`), a `SessionLocal` sessionmaker, and a `get_db()` generator (yield session, always close). Use **synchronous** SQLAlchemy. It is simpler to debug for an FYP, and FastAPI runs sync endpoints in a threadpool. Do not introduce async sessions unless the team asks.

### `scripts/check_db.py`
Connects using `DATABASE_URL`, runs `SELECT 1`, prints the Postgres version, and prints whether the `vector` extension is installed. Exit code non-zero on failure.

**Verification:** `python -m scripts.check_db` prints a successful connection.

---

## Phase 5 — SQLAlchemy Models

### Conventions for every model
- Table names are plural snake_case (`users`, `projects`, `journals`, ...).
- Integer primary keys with identity/autoincrement (matches the report).
- All timestamps are `DateTime(timezone=True)` with `server_default=func.now()`.
- Enum-like columns use `sa.Enum(..., native_enum=False, create_constraint=True, name="...")` so they become CHECK constraints (easier migrations than native PG enums).
- Every relationship defines both sides (`back_populates`) and explicit `ondelete` behavior on the FK.
- Use `Mapped[...]` type hints and `from __future__ import annotations` carefully; keep imports of related models inside `TYPE_CHECKING` to avoid circular imports.
- `app/db/models/__init__.py` must import all models so `Base.metadata` is complete for Alembic.

### 5.1 `users`

| Column | Type | Constraints |
|---|---|---|
| user_id | Integer | PK |
| full_name | String(150) | NOT NULL |
| email | String(255) | NOT NULL, **unique on `lower(email)`** (functional unique index) |
| password_hash | String(255) | NOT NULL |
| role | Enum(`researcher`, `admin`) | NOT NULL, default `researcher` |
| created_at | DateTime(tz) | NOT NULL, default now |

Relationships: `projects` (one-to-many, cascade delete).

### 5.2 `projects`

| Column | Type | Constraints |
|---|---|---|
| project_id | Integer | PK |
| user_id | Integer | FK → users.user_id, NOT NULL, ON DELETE CASCADE, indexed |
| project_title | String(300) | NOT NULL |
| manuscript_abstract | Text | NULL |
| current_file_path | String(500) | NULL |
| file_deleted_at | DateTime(tz) | NULL (set when the temp file is purged) (D5) |
| summary_text | Text | NULL |
| created_at | DateTime(tz) | NOT NULL, default now |

Relationships: `owner`, `project_journals`, `conversion_jobs`, `compliance_reports` (all cascade delete).

### 5.3 `journals`

| Column | Type | Constraints |
|---|---|---|
| journal_id | Integer | PK |
| journal_title | String(400) | NOT NULL, indexed |
| publisher | String(200) | NOT NULL, indexed |
| issn | String(20) | NULL, **unique** (multiple NULLs allowed) |
| subject_category | String(200) | NULL, indexed |
| citescore | Float | NULL |
| impact_factor | Float | NULL |
| quartile | Enum(`Q1`,`Q2`,`Q3`,`Q4`) | NULL |
| aims_and_scope | Text | NOT NULL |
| open_access_type | String(50) | NULL (e.g. `open_access`, `subscription`, `hybrid`) |
| review_weeks | Integer | NULL, CHECK `>= 0` |
| acceptance_rate | Float | NULL, CHECK between 0 and 100 |
| embedding | `Vector(768)` (pgvector) | NULL (D1) |
| embedding_model | String(100) | NULL (records which model made the vector) |
| created_at | DateTime(tz) | NOT NULL, default now |

Index: **HNSW** on `embedding` with cosine ops:

```python
Index(
    "ix_journals_embedding_hnsw",
    "embedding",
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
```

Relationships: `guideline_rules`, `templates`, `project_matches` (to `project_journals`).

### 5.4 `project_journals`

| Column | Type | Constraints |
|---|---|---|
| project_journal_id | Integer | PK |
| project_id | Integer | FK → projects, NOT NULL, ON DELETE CASCADE |
| journal_id | Integer | FK → journals, NOT NULL, ON DELETE RESTRICT |
| similarity_score | Float | NULL (empty for manual picks) |
| is_selected | Boolean | NOT NULL, default false |
| added_at | DateTime(tz) | NOT NULL, default now |

Constraints: **UNIQUE (project_id, journal_id)** (D7). Additionally, a **partial unique index** so a project has at most one selected target journal:
`UNIQUE (project_id) WHERE is_selected = true`.

### 5.5 `guideline_rules`

| Column | Type | Constraints |
|---|---|---|
| rule_id | Integer | PK |
| journal_id | Integer | FK → journals, NULL, ON DELETE SET NULL (NULL = rules from a user-supplied URL for a journal not in the catalog) |
| source_url | String(1000) | NULL |
| rules | **JSONB** | NOT NULL, default `'{}'` (D2) |
| version | Integer | NOT NULL, default 1 |
| is_active | Boolean | NOT NULL, default true |
| updated_at | DateTime(tz) | NOT NULL, default now, onupdate now |

Index: `(journal_id, is_active)`. Optional GIN index on `rules` — only add if querying inside the JSON becomes necessary.

**Recommended shape of the `rules` JSON** (document this in `README.md`; the compliance engine will read it later; all keys optional):

```json
{
  "max_word_count": 8000,
  "max_abstract_words": 250,
  "citation_style": "IEEE",
  "required_sections": ["Abstract", "Introduction", "Methodology", "Conclusion", "References"],
  "column_layout": "double",
  "required_statements": ["Conflict of Interest", "Data Availability"],
  "font": { "family": "Times New Roman", "size_pt": 10 },
  "margins_cm": { "top": 2.5, "bottom": 2.5, "left": 2.0, "right": 2.0 },
  "keywords": { "min": 3, "max": 6 }
}
```

Add a `CHECK (jsonb_typeof(rules) = 'object')` constraint so it is always a JSON object.

### 5.6 `templates`

| Column | Type | Constraints |
|---|---|---|
| template_id | Integer | PK |
| journal_id | Integer | FK → journals, NULL, ON DELETE CASCADE |
| rule_id | Integer | FK → guideline_rules, NULL, ON DELETE SET NULL |
| template_format | Enum(`latex`, `word`) | NOT NULL |
| template_file_path | String(500) | NOT NULL |
| is_generated | Boolean | NOT NULL, default false |
| created_at | DateTime(tz) | NOT NULL, default now |

### 5.7 `conversion_jobs`

| Column | Type | Constraints |
|---|---|---|
| job_id | Integer | PK |
| project_id | Integer | FK → projects, NOT NULL, ON DELETE CASCADE, indexed |
| conversion_type | Enum(`format_conversion`, `manuscript_transformation`) | NOT NULL (D4) |
| source_format | Enum(`docx`, `tex`) | NULL |
| target_format | Enum(`docx`, `tex`) | NULL |
| source_journal_id | Integer | FK → journals, NULL, ON DELETE SET NULL (D3) |
| target_journal_id | Integer | FK → journals, NULL, ON DELETE SET NULL (D3) |
| target_guideline_id | Integer | FK → guideline_rules, NULL, ON DELETE SET NULL (D3) |
| conversion_status | Enum(`pending`, `completed`, `failed`) | NOT NULL, default `pending` |
| output_file_path | String(500) | NULL |
| error_message | Text | NULL (useful for debugging failed jobs) |
| created_at | DateTime(tz) | NOT NULL, default now |

### 5.8 `compliance_reports`

| Column | Type | Constraints |
|---|---|---|
| report_id | Integer | PK |
| project_id | Integer | FK → projects, NOT NULL, ON DELETE CASCADE, indexed |
| journal_id | Integer | FK → journals, NULL, ON DELETE SET NULL |
| rule_id | Integer | FK → guideline_rules, NULL, ON DELETE SET NULL |
| overall_status | Enum(`passed`, `failed`) | NOT NULL |
| passed_checks | Integer | NOT NULL, default 0, CHECK `>= 0` |
| failed_checks | Integer | NOT NULL, default 0, CHECK `>= 0` |
| report_pdf_path | String(500) | NULL |
| generated_at | DateTime(tz) | NOT NULL, default now |

### 5.9 `compliance_issues`

| Column | Type | Constraints |
|---|---|---|
| issue_id | Integer | PK |
| report_id | Integer | FK → compliance_reports, NOT NULL, ON DELETE CASCADE, indexed |
| rule_type | String(100) | NOT NULL (e.g. `max_word_count`) |
| severity | Enum(`error`, `warning`) | NOT NULL |
| message | Text | NOT NULL |
| suggested_fix | Text | NULL |

### Delete behaviour summary (document in README)

- Deleting a **user** → deletes their projects → deletes all their matches, jobs, reports and issues.
- Deleting a **journal** that any project has matched is **blocked** (RESTRICT). Journals are catalog data; deactivate rather than delete.
- Deleting a journal or rule referenced by jobs/reports/templates **keeps** those rows with the reference set to NULL.

**Verification:** `python -c "from app.db.models import *; from app.db.base import Base; print(sorted(Base.metadata.tables))"` lists all nine tables.

---

## Phase 6 — Alembic Setup & Initial Migration

Tasks:
1. Run `alembic init alembic` inside `backend/`.
2. Edit `alembic/env.py`:
   - Load `DATABASE_URL` from app settings (not hard-coded in `alembic.ini`; leave `sqlalchemy.url` blank there).
   - `from app.db.base import Base` and `import app.db.models` so all tables are registered; set `target_metadata = Base.metadata`.
   - Enable `compare_type=True`.
3. Generate the first migration: `alembic revision --autogenerate -m "initial schema"`.
4. **Manually edit the generated migration** (autogenerate will not do these for you):
   - At the very top of `upgrade()`, add: `op.execute("CREATE EXTENSION IF NOT EXISTS vector")`.
   - Add `import pgvector.sqlalchemy` to the migration file so the `Vector` type resolves.
   - Verify the HNSW index uses `vector_cosine_ops`.
   - Verify the functional unique index on `lower(email)` and the partial unique index on `project_journals` exist (add with `op.create_index(..., postgresql_where=...)` if autogenerate missed them).
   - Verify CHECK constraints for the enum-like columns and numeric ranges.
   - In `downgrade()`, drop the tables in reverse dependency order. Do **not** drop the `vector` extension.
5. Review the migration file in full and show it to the user before applying.
6. Apply: `alembic upgrade head`.

**Verification:**
- `alembic current` shows the head revision.
- In psql: `\dt` shows 9 tables + `alembic_version`; `\d journals` shows the `embedding vector(768)` column and the HNSW index.
- Round trip works: `alembic downgrade base` then `alembic upgrade head` completes with no errors.

---

## Phase 7 — Seed Data

**Goal:** a small but *real* journal catalog so recommendations can be tested. Do not try to load the entire journal universe.

### 7.1 `seed/journals.csv`
Columns: `journal_title, publisher, issn, subject_category, citescore, impact_factor, quartile, aims_and_scope, open_access_type, review_weeks, acceptance_rate`.

- Target **50–100 journals** across at least 5 subject areas (e.g. computer science, AI/ML, software engineering, information systems, data science) and across the report's publishers (IEEE, Elsevier, Springer Nature, ACM, Wiley).
- `aims_and_scope` must be the real, human-readable scope text. It is what the embeddings are built from, so quality matters more than quantity.
- Leave `acceptance_rate`, `review_weeks` and `impact_factor` **empty** when no reliable public source exists. Never invent numbers; the UI will show "N/A". Tell the user which columns were hard to fill.
- Agent note: do not fabricate journal data. If you cannot source real values, generate only the **structure** (a CSV template with 3–5 example rows clearly marked as samples) and ask the user to fill in the rest or point to a data source (e.g. open scholarly metadata sources).

### 7.2 `scripts/seed_journals.py`
- Reads the CSV, validates each row (types, ranges), and **upserts by ISSN** (fall back to `(journal_title, publisher)` when ISSN is empty) so the script is safely re-runnable.
- Prints counts: inserted / updated / skipped (with reasons).
- Runs in a single transaction; rolls back on error.

### 7.3 `scripts/seed_dev_data.py` (development only)
Creates one demo researcher user, one admin user, one demo project, and one sample `guideline_rules` row (using the JSON shape in 5.5) for a seeded journal. Refuse to run if an env var `APP_ENV=production`. Use a placeholder `password_hash` string (the real hashing is implemented in the auth phase, not here).

**Verification:** run each script twice; the second run inserts nothing new and creates no duplicates.

---

## Phase 8 — Journal Embeddings

**Goal:** fill `journals.embedding` so the matching engine can run vector search.

Tasks:
1. Install `requirements-embeddings.txt` (separate step; heavy download — warn the user).
2. Write `scripts/embed_journals.py`:
   - Load the SPECTER embedding model through sentence-transformers (the report names SPECTER; the `allenai-specter` checkpoint produces **768-dim** vectors). **Check the model's output dimension programmatically and abort if it is not 768.**
   - Select journals where `embedding IS NULL` (or all, with a `--force` flag).
   - Embed in **batches** (e.g. 16–32) using `journal_title + ". " + aims_and_scope`.
   - Write the vector and set `embedding_model` to the model name. Commit per batch.
   - Print progress and a final summary.
3. Add a `--limit N` flag for quick tests.

**Verification (the real test of the whole schema):** write a small snippet/test that embeds a sample abstract with the same model and runs:

```sql
SELECT journal_id, journal_title,
       1 - (embedding <=> :query_vector) AS similarity
FROM journals
WHERE embedding IS NOT NULL
ORDER BY embedding <=> :query_vector
LIMIT 5;
```

Results should be sensible (an ML abstract should surface ML/AI journals). Confirm with `EXPLAIN` that the HNSW index is used once the table is large enough (on a tiny table Postgres may legitimately choose a sequential scan; that is fine).

---

## Phase 9 — Tests

Use `pytest` against `TEST_DATABASE_URL` (the `publishaid_test` DB). `tests/conftest.py` should: run `alembic upgrade head` once per session on the test DB, wrap each test in a transaction that rolls back, and never touch the dev database.

`tests/test_schema.py` must cover:

- All 9 tables exist; the `vector` extension is installed.
- Email uniqueness is case-insensitive (`A@x.com` vs `a@x.com` → IntegrityError).
- Invalid enum value (e.g. `role='superuser'`) → IntegrityError.
- Duplicate `(project_id, journal_id)` in `project_journals` → IntegrityError.
- Two selected journals for one project → IntegrityError (partial unique index).
- Deleting a user cascades through projects, matches, jobs, reports and issues.
- Deleting a journal that is matched to a project → blocked.
- Deleting a journal referenced by a `guideline_rules`/`templates`/`conversion_jobs` row behaves per the delete summary (SET NULL / CASCADE as defined).
- `guideline_rules.rules` rejects a JSON array (CHECK constraint) and accepts the sample object.
- A `Vector(768)` value round-trips, and a wrong-length vector is rejected.
- `acceptance_rate = 150` and `review_weeks = -1` are rejected.

**Verification:** `pytest -q` is fully green.

---

## Phase 10 — Documentation & Handoff

Create `backend/README.md` with:

1. Prerequisites and **exact setup commands** (docker compose up, venv, pip install, copy `.env`, `alembic upgrade head`, seed scripts, embed script).
2. How to create a new migration and how to roll back.
3. The schema overview (table list + relationship summary).
4. The deviations table (D1–D7) so the team can update the FYP report's ER diagram and data dictionary to match.
5. The `rules` JSON shape.
6. A short "Next steps" section: FastAPI app skeleton, JWT auth + password hashing, CRUD endpoints, CORS configuration for the frontend dev server, then the matching endpoint.
7. Troubleshooting: port 5432 in use, `vector` extension missing, Alembic can't find models, Windows line-ending issues, password auth failures after changing `.env` (the Docker volume keeps the old password until you run `docker compose down -v`).

---

## Final Acceptance Checklist

The database phase is complete only when **all** are true:

- [ ] `docker compose up -d` starts a healthy PostgreSQL + pgvector container.
- [ ] `alembic upgrade head` builds all 9 tables on a clean database; `downgrade base` / `upgrade head` round-trips.
- [ ] `journals.embedding` is `vector(768)` with an HNSW cosine index.
- [ ] `guideline_rules.rules` is JSONB and constrained to JSON objects.
- [ ] All seed scripts are idempotent.
- [ ] Embeddings are generated and a sample similarity query returns sensible journals.
- [ ] `pytest -q` is green.
- [ ] `backend/README.md` is complete and includes the deviations table.
- [ ] **`git diff --stat -- frontend/` prints nothing, and `git status` shows no changes under `frontend/`.**
- [ ] No secrets committed; only `.env.example` is tracked.

---

## Appendix A — Suggested Prompts for Antigravity

Use one prompt per phase. Start each with the Hard Rules block from Section 0.

**Phase 1–3**
> Read `PublishAid_Database_Plan.md`. Execute Phases 1 to 3 only. Do not touch `frontend/`. Create everything inside a new `backend/` folder. When finished, show me the commands you ran and their output, then stop.

**Phase 4–5**
> Execute Phases 4 and 5 of `PublishAid_Database_Plan.md`. Implement all nine models exactly as specified, including the deviations D1–D7. Show me the list of created files, then stop. Do not generate migrations yet.

**Phase 6**
> Execute Phase 6. Generate the initial Alembic migration, then manually apply every fix listed in the plan. Show me the complete migration file for review **before** running `alembic upgrade head`.

**Phase 7–8**
> Execute Phases 7 and 8. Never invent journal data. If you cannot source real values, build the CSV structure with clearly marked sample rows and tell me what I need to fill in.

**Phase 9–10**
> Execute Phases 9 and 10, then run the Final Acceptance Checklist and report every item as pass/fail. Finish by running `git diff --stat -- frontend/` and showing me the (empty) output.

## Appendix B — Why these choices (for your viva)

- **PostgreSQL + JSONB:** strict relational integrity for users/projects/jobs, flexible JSON for publisher rules that change often, with no migration needed when a publisher adds a new requirement.
- **pgvector instead of a separate vector database:** one database to run, back up and explain; transactional consistency between journal metadata and its embedding; sufficient for a catalog of this size.
- **HNSW + cosine distance:** the standard approach for semantic similarity of document embeddings, with good recall and no training step.
- **CHECK constraints instead of native PG enums:** simpler, safer migrations when allowed values change.
- **Alembic migrations:** every schema change is versioned and reproducible, so all three team members and any deployment get the identical database.
- **Metadata-only persistence:** the DB never stores manuscript contents, consistent with the report's privacy strategy (5.4.3); only paths, statuses and audit results are retained.
