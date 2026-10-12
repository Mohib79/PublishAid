# PublishAid Backend — Database Layer

This directory contains the database layer for PublishAid: PostgreSQL with `pgvector`, SQLAlchemy 2.0 ORM models, Alembic migrations, database seeding scripts, SPECTER journal embeddings, and automated schema tests.

---

## 1. Prerequisites & Quick Start

### Prerequisites
* **Python 3.10+** (Tested on Python 3.10.11)
* **Docker Desktop** (with Docker Compose)
* **Git**

### Setup Commands (from project root)

```bash
# 1. Navigate to backend
cd backend

# 2. Start PostgreSQL + pgvector container
# Note: Host port 5433 is used to avoid collision if port 5432 is already bound
docker compose up -d

# 3. Create the test database inside the container
docker exec publishaid_db psql -U publishaid -c "CREATE DATABASE publishaid_test;"

# 4. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate   # On Windows PowerShell
# source .venv/bin/activate  # On Linux/macOS

# 5. Install base requirements
pip install -r requirements.txt

# 6. Verify connection to the database
python -m scripts.check_db

# 7. Apply Alembic migrations
alembic upgrade head

# 8. Seed journal catalog and development data
python -m scripts.seed_journals
python -m scripts.seed_dev_data

# 9. (Optional / Embeddings) Install heavy embedding packages & generate vectors
pip install -r requirements-embeddings.txt
python -m scripts.embed_journals

# 10. Run automated tests
pytest -q
```

---

## 2. Managing Migrations (Alembic)

All schema changes must go through Alembic migrations. Never modify tables manually.

* **Generate a new migration after editing models:**
  ```bash
  alembic revision --autogenerate -m "describe your changes"
  ```
* **Apply all pending migrations:**
  ```bash
  alembic upgrade head
  ```
* **Roll back the latest migration:**
  ```bash
  alembic downgrade -1
  ```
* **Roll back all migrations:**
  ```bash
  alembic downgrade base
  ```
* **View current revision:**
  ```bash
  alembic current
  ```

---

## 3. Schema Overview

The database contains 9 relational tables:

| Table Name | Primary Key | Description |
|---|---|---|
| `users` | `user_id` | User accounts (`researcher`, `admin`) with case-insensitive unique email index. |
| `projects` | `project_id` | Research projects / manuscripts owned by a user. |
| `journals` | `journal_id` | Academic journals catalog with metadata, `vector(768)` embedding, and HNSW cosine index. |
| `project_journals` | `project_journal_id` | Association between projects and shortlisted journals, with match scores and selection flag. |
| `guideline_rules` | `rule_id` | Publisher submission rules stored as flexible JSONB. |
| `templates` | `template_id` | LaTeX / Word manuscript templates linked to journals and guidelines. |
| `conversion_jobs` | `job_id` | Format conversion and transformation tracking. |
| `compliance_reports` | `report_id` | Automated guideline compliance audits for manuscripts. |
| `compliance_issues` | `issue_id` | Individual issues detected during compliance checks. |

### Cascade & Deletion Rules
* **User deleted:** Cascades delete to projects, jobs, reports, issues, and shortlisted journals.
* **Journal deleted:** Deletion is blocked (`RESTRICT`) if matched in `project_journals`. Referenced rows in `conversion_jobs`, `compliance_reports`, and `guideline_rules` set their foreign key to `NULL`. Referenced `templates` cascade delete.

---

## 4. FYP Report Deviations (D1 – D7)

The following refinements resolve inconsistencies found in the FYP report data dictionary:

| ID | FYP Report Specification | Implemented In Code | Rationale |
|---|---|---|---|
| **D1** | `Journal` had no embedding column | Added `embedding vector(768)` + HNSW cosine index | Section 5.3.2.2 requires semantic vector matching directly inside the DB. |
| **D2** | `GuidelineRule` had rigid columns (`max_word_count`, `citation_style`, etc.) | Stored inside `rules JSONB` with `CHECK (jsonb_typeof(rules) = 'object')` | Section 5.4.2 requires formatting guidelines decoupled from database schema. |
| **D3** | `ConversionJob` foreign keys typed as `String` | Changed to `Integer` Foreign Keys | Properly references Integer PKs on referenced tables. |
| **D4** | `ConversionJob.conversion_type` was integer `0/1` | String Enum: `format_conversion`, `manuscript_transformation` | Self-documenting values; prevents magic numbers. |
| **D5** | `Project.current_file_path` always present | Nullable `current_file_path` + added `file_deleted_at` | Section 5.4.3 states manuscripts are purged after the session for privacy. |
| **D6** | Status and role fields were unconstrained strings | Constrained with `sa.Enum(..., native_enum=False, create_constraint=True)` | Generates clean SQL CHECK constraints to prevent invalid states. |
| **D7** | No uniqueness on `ProjectJournal` | Added `UNIQUE (project_id, journal_id)` and partial unique index `(project_id) WHERE is_selected = true` | Prevents duplicate journal bookmarks; ensures at most 1 selected journal per project. |

---

## 5. Shape of the Guideline `rules` JSONB Object

Formatting and guideline specifications are stored in `guideline_rules.rules`:

```json
{
  "max_word_count": 8000,
  "max_abstract_words": 250,
  "citation_style": "IEEE",
  "required_sections": [
    "Abstract",
    "Introduction",
    "Methodology",
    "Conclusion",
    "References"
  ],
  "column_layout": "double",
  "required_statements": [
    "Conflict of Interest",
    "Data Availability"
  ],
  "font": {
    "family": "Times New Roman",
    "size_pt": 10
  },
  "margins_cm": {
    "top": 2.5,
    "bottom": 2.5,
    "left": 2.0,
    "right": 2.0
  },
  "keywords": {
    "min": 3,
    "max": 6
  }
}
```

---

## 6. Next Steps (API & Engine Integration)

1. **FastAPI Application Skeleton**:
   * Create `app/main.py` with CORS middleware configured for the Vite frontend (`http://localhost:5173`).
2. **Authentication & Security**:
   * Implement JWT token generation, OAuth2 password flow, and `bcrypt` / `argon2` password hashing.
3. **CRUD API Endpoints**:
   * `/api/projects`: manuscript creation, list, update.
   * `/api/journals`: catalog search, filtering by quartile, acceptance rate, cite score.
   * `/api/matching`: semantic journal recommendation endpoint querying `journals.embedding <=> :query_vector`.
   * `/api/compliance`: run rule validation and generate reports.
4. **Document Processing Engine**:
   * Connect pandoc / docx / latex transformation pipeline.

---

## 7. Troubleshooting

* **Port 5432 in use:**
  If a local PostgreSQL server runs on host port 5432, Docker maps to host port 5433 (`5433:5432`). Ensure `DATABASE_URL` uses `localhost:5433`.
* **Database password authentication fails after `.env` change:**
  PostgreSQL stores password hashes in the Docker volume. Run `docker compose down -v` and `docker compose up -d` to reset the volume with new credentials.
* **Vector extension missing:**
  The migration runs `CREATE EXTENSION IF NOT EXISTS vector;` on the `pgvector/pgvector:pg16` image. If using a custom PostgreSQL install, ensure the pgvector package is installed.
* **ModuleNotFoundError: No module named 'app':**
  Run scripts as modules from the `backend/` directory:
  ```bash
  python -m scripts.check_db
  ```
## 8.Update journal table
To reset current journal table in db and to repopulate with journals in journals.csv 
run:
```bash
python -m scripts.seed_journals
```