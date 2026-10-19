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

## 6. Journal Finder & Semantic Matching Engine

### Overview
PublishAid implements semantic journal discovery powered by the `allenai-specter` scientific embedding transformer (768-dimensional space) and PostgreSQL `pgvector` with HNSW cosine indexing.

### Endpoints
* **`POST /journals/match`** (and `/api/journals/match`):
  * Body: `{ "title": "...", "abstract": "...", "keywords": ["..."], "limit": 20, "projectId": "optional" }`
  * Response: Ranked array of journals with `matchScore` (0-100), `rawSimilarity` (0.0-1.0), `matchTag` ("Best fit" for rank 1), and `isShortlisted` flag.
  * Validation: Requires authentication. At least `title` or `abstract` must be non-empty (422 otherwise). If `projectId` belongs to another user, returns 404.
* **`POST /projects`** (and `/api/projects`):
  * Body: `{ "title": "...", "abstract": "...", "keywords": ["..."] }`
  * Returns created project. Auto-created when a user shortlists a journal without an active project.
* **`PUT /projects/{projectId}/shortlist/{journalId}`**:
  * Body: `{ "similarityScore": 0.88 }` (optional)
  * Idempotently shortlists the journal for the project and returns the updated journal item.
* **`DELETE /projects/{projectId}/shortlist/{journalId}`**:
  * Removes journal from the project shortlist.
* **`GET /projects/{projectId}/shortlist`**:
  * Returns all shortlisted journals for the specified project.

### Matching Score Computation & Ranking Rationale
* The manuscript query text is constructed using the SPECTER convention: `title + "\n\n" + abstract + (keywords ? "\n\nKeywords: " + ", ".join(keywords) : "")`.
* Cosine distance is queried using pgvector operator `<=>`: `distance = Journal.embedding.cosine_distance(query_vector)`.
* Raw similarity is defined as `raw_similarity = 1.0 - distance`.
* The `matchScore` percentage is computed by clamping raw similarity to `[0.0, 1.0]` and rounding: `int(round(clamped * 100))`.
* **Note on percentages:** In scientific embedding spaces (SPECTER), cosine similarity typically falls between 0.65 and 0.90 for domain-relevant papers. Therefore, **ordinal rank** (1st, 2nd, 3rd) provides the true measure of topical fit, while the percentage serves as an intuitive visual signal.

### Running the Evaluation Harness
PublishAid includes a benchmark suite containing 20 real research papers across the 50 catalog journals.
```bash
python -m scripts.eval_matching
```
Results on the 20-case benchmark (`backend/eval/results_2026-10-19.md`):
* **Top-1 Accuracy:** **55.0%** (11/20)
* **Top-3 Accuracy:** **85.0%** (17/20)
* **Top-5 Accuracy:** **95.0%** (19/20)
* **Mean Reciprocal Rank (MRR):** **0.6884**
* **Mean Top Similarity:** `0.8296`
* **Mean Rank 1–5 Gap:** `0.0596`

### Known Limitations
* **Curated Catalog:** 50 verified journals currently in the database.
* **No File Text Extraction Yet:** Manuscript file uploads must currently have title/abstract entered manually; PDF/DOCX parsing will be introduced in a dedicated phase.
* **Nullable Metrics:** Metrics (`citeScore`, `reviewWeeks`, `acceptanceRate`) that are unverified in external registries return `null` and are rendered as `"N/A"` in the UI (never fabricated).

---

## 7. Next Milestones

1. **Projects & Dashboard Wiring**: Connect project status pills, dynamic project switching, and persistent activity history.
2. **Compare Page Wiring**: Wire live compare table using shortlisted journals from `GET /projects/{id}/shortlist`.
3. **File Extraction Pipeline**: Automated PDF/DOCX title, abstract, and text parser.
4. **Guideline Rules & Compliance Checker**: Automated manuscript compliance evaluation against journal submission guidelines.

---

## 8. Troubleshooting

* **Port 5434 in use:**
  If a local PostgreSQL server runs on port 5432 or 5433, Docker maps to host port 5434 (`5434:5432`). Ensure `DATABASE_URL` uses `localhost:5434`.
* **Database password authentication fails after `.env` change:**
  PostgreSQL stores password hashes in the Docker volume. Run `docker compose down -v` and `docker compose up -d` to reset the volume with new credentials.
* **Vector extension missing:**
  The migration runs `CREATE EXTENSION IF NOT EXISTS vector;` on the `pgvector/pgvector:pg16` image.
* **Reset & Re-seed Journals:**
  ```bash
  python -m scripts.seed_journals --reset
  python -m scripts.embed_journals --force
  ```