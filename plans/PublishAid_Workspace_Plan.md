# PublishAid — Workspace Creation Plan (Plan 3)

**Feature:** Create and manage manuscript workspaces (projects): create, list, open, edit, delete, attach a draft file, set a target journal, and see an activity log.
**Audience:** Antigravity / Claude Code (implementation) and the team (review, testing, viva).
**Requires first:** Database plan, Auth plan, and ideally the Journal Data and Journal Finder plans (this plan extends the project and shortlist work started there; see Phase W1).
**Report references:** Use Case 4.3 *Create Manuscript Workspace*; Functional Requirement "Users can set up manuscript projects, upload draft files, attach target journals, and view previous validation reports"; Section 5.1.1 *Authentication & Workspace Management Module*; Section 5.3.2.3 *Temporary Execution Storage*.

Order of all plans: Database -> Auth -> Journal Data -> Journal Finder -> **Workspace (this file)** -> Guidelines -> Conversion -> Compliance.

---

## 1. What a workspace is

A **workspace** is the project folder for one manuscript. Everything PublishAid does for a paper (finding journals, comparing them, extracting guidelines, converting, checking compliance) needs somewhere to attach its results. The workspace is that place. Without it, each feature would produce an answer and then forget it.

In the database a workspace is a row in the `projects` table. In the product it is the screen the researcher opens to continue working on one paper.

### What lives inside a workspace

| Item | Where it is stored | Built in |
|---|---|---|
| Title, research field, abstract, keywords, status | `projects` table | **This plan** |
| Shortlisted journals and the one **target journal** | `project_journals` table | Shortlist: Finder plan. Target journal: **this plan** |
| The current draft file (.docx, .tex, .pdf) | **Temporary disk storage**, metadata in `projects` | **This plan** (Part B) |
| Activity (audit) log: who did what and when | `activity_logs` table (new) | **This plan** |
| Conversion jobs | `conversion_jobs` table | Conversion plan |
| Compliance reports | `compliance_reports` / `compliance_issues` tables | Compliance plan |
| Paper summary | `projects.summary_text` | Summarization plan |

### What a researcher can do (user stories)

1. As a researcher, I create a new project with a title and my research field so that I have a place for my paper.
2. I see all my projects on my dashboard, newest activity first, and I can search and filter them.
3. I open a project and see its overview: details, shortlisted journals, target journal, draft file, recent activity.
4. I edit the project's details, or delete it when I no longer need it.
5. I attach my draft file to the project. I know it is temporary and will be deleted automatically.
6. I choose one shortlisted journal as my target. Later features (templates, conversion, compliance) use it.
7. I can see a history of what happened in my projects.

### Mapping to the report's use case (Table 4.3)

| Report step | What the system does in this plan |
|---|---|
| 1. Author clicks **New Project** | Frontend opens the modal (already designed) |
| 1.1 System asks for project title and primary research field | Modal fields: `title` (required), `researchField` (optional) |
| 2. Author confirms | `POST /projects` |
| 2.1 System initializes the workspace and shows a success notification | Row created, `project_created` activity logged, `201` returned, frontend shows the notification |
| 3. Author selects the project from the list | `GET /projects/{id}` returns the overview |
| 3.1 System opens the workspace overview, ready for manuscript uploads | Overview page with the upload area (Part B) |
| Alt flow 3-A: blank title | Backend returns `422`; frontend shows "enter a title" inline and does not submit |

---

## 2. How it fits together

```
React (frontend)                FastAPI (backend)                    Storage
-----------------               ------------------------------      -----------------------------
Projects page         ---->     /projects  (CRUD, list, overview)   PostgreSQL
New Project modal     ---->     /projects/{id}/target-journal       - projects
Workspace overview    ---->     /projects/{id}/manuscript           - project_journals
Dashboard activity    ---->     /projects/{id}/activity             - activity_logs
                                /activity/recent
                                        |                            Temporary disk (STORAGE_ROOT)
                                        +--> services: projects,     - one folder per project
                                             storage, activity       - UUID file names
                                        +--> background cleanup      - auto-deleted after TTL
```

Three rules hold everywhere:

1. **Everything is owner-scoped.** A user can only see and change their own projects. Someone else's project returns `404`, never `403`, so IDs can't be probed.
2. **The database holds metadata only.** No manuscript text, no abstract text in logs, no absolute file paths in responses.
3. **Files are temporary.** A file lives in the workspace only until the user removes it, deletes the project, or the time limit passes.

---

## 3. Decisions

### 3.1 Decisions already made

| Topic | Decision |
|---|---|
| Terminology | "Workspace" in the UI and report, `projects` table and `/projects` endpoints in code |
| Ownership | One owner per project. No sharing or collaboration in this plan |
| Deleting | Hard delete with cascade (matches the schema). The frontend must show a confirmation. Archiving is future work |
| IDs | Integer in the database and URL, **string** in JSON (same as auth) |
| JSON style | camelCase (same alias generator as auth) |
| Not found vs forbidden | Always `404` for another user's data |
| One draft file per project | Version 1 keeps a single current manuscript file. Version history is future work |
| Bibliography (.bib), asset folders, zip projects | Not handled here. They belong to the Conversion plan |
| File contents | Stored but **not parsed** in this plan. No text extraction |
| Frontend edits | Allowed only to the files approved in Phase W1 |

### 3.2 Open decisions with defaults (agent uses the default unless told otherwise)

| Topic | Default | Why |
|---|---|---|
| Status values | `draft`, `in_progress`, `ready_to_submit`, `submitted` in DB and API; mapped in the UI to `StatusBadge` labels (`Draft`, `Formatting` / `In progress`, `Ready to submit`, `Submitted`) | Keeps DB/API tokens normalized while reusing `StatusBadge.tsx` without restyling |
| Research field | Free text, optional, up to 150 characters | The report's modal asks for it but doesn't require it |
| Maximum projects per user | 50 (setting `MAX_PROJECTS_PER_USER`) | Protects the database from runaway creation |
| Duplicate titles | Allowed | Researchers may legitimately reuse a title |
| Allowed draft file types | `.docx`, `.tex`, `.pdf` | Matches the finder page's upload zone and the report's conversion scope |
| Maximum draft size | 20 MB (`MAX_UPLOAD_MB`) | The existing UI text says 20 MB |
| File time-to-live | 120 minutes after upload (`WORKSPACE_FILE_TTL_MINUTES`) | Implements "deleted post-session" from Section 5.3.2.3 |
| Cleanup interval | Every 10 minutes (`CLEANUP_INTERVAL_MINUTES`) | Frequent enough for the TTL |
| Status changes | Any valid status to any valid status (no state machine yet) | Keeps v1 simple |

---

## 4. Data model changes

All changes go through **one Alembic migration** (show it before applying).

### 4.1 `projects` table: new columns

| Column | Type | Rules |
|---|---|---|
| `research_field` | String(150) | NULL |
| `status` | String(30) | NOT NULL, default `draft`, CHECK in the allowed set |
| `updated_at` | DateTime(tz) | NOT NULL, default now, `onupdate` now. Backfill existing rows with `created_at` |
| `manuscript_filename` | String(255) | NULL. Sanitized **display** name only, never used as a path |
| `manuscript_size_bytes` | BigInteger | NULL, CHECK `>= 0` |
| `manuscript_uploaded_at` | DateTime(tz) | NULL |

Existing columns reused: `current_file_path` (store a **relative** key like `<project_id>/<uuid>.docx`, never an absolute path), `file_deleted_at` (set when the file is purged or removed), `keywords` (added in the Finder plan; add it here if missing), `summary_text`.

Constraints to add:
- CHECK `char_length(btrim(project_title)) > 0` (no blank titles at the database level).
- Index `(user_id, updated_at DESC)` for the project list.
- Index `(user_id, status)` for filtering.

### 4.2 `project_journals` table

- Add `is_shortlisted` (Boolean, NOT NULL, default false) if the Finder plan has not already.
- Add CHECK `NOT is_selected OR is_shortlisted` (a target journal is always shortlisted). Before adding it, backfill: `UPDATE project_journals SET is_shortlisted = true WHERE is_selected`.
- Keep the unique `(project_id, journal_id)` and the partial unique index "at most one `is_selected` per project".

### 4.3 New table `activity_logs` (the audit log promised in Section 5.1.1)

This table is a deliberate addition to the report's nine-table design (document it as deviation **D8** in `backend/README.md` so the ER diagram can be updated).

| Column | Type | Rules |
|---|---|---|
| `log_id` | Integer | PK |
| `user_id` | Integer | FK to users, NOT NULL, ON DELETE CASCADE |
| `project_id` | Integer | FK to projects, NULL, ON DELETE **SET NULL** |
| `project_title` | String(300) | NULL. Snapshot of the title at the time, so history stays readable after a project is deleted |
| `event_type` | String(50) | NOT NULL. Validated in code with an enum (no database CHECK, because later features add new events) |
| `details` | JSONB | NOT NULL, default `{}`, CHECK `jsonb_typeof(details) = 'object'` |
| `created_at` | DateTime(tz) | NOT NULL, default now |

Indexes: `(user_id, created_at DESC)` and `(project_id, created_at DESC)`.

**Event types for this plan:** `project_created`, `project_updated`, `project_status_changed`, `project_deleted`, `manuscript_uploaded`, `manuscript_removed`, `manuscript_purged`, `journal_shortlisted`, `journal_unshortlisted`, `target_journal_set`, `target_journal_cleared`. (Later plans add `conversion_completed`, `compliance_report_generated`, `summary_generated`.)

**Privacy rule for `details`:** only small, whitelisted facts. Never the abstract, the title text, the file name or any manuscript content. Allowed examples: `{"fields": ["title", "researchField"]}`, `{"from": "draft", "to": "in_progress"}`, `{"extension": "docx", "sizeBytes": 183422, "replaced": true}`, `{"journalId": 7}`.

---

## 5. API contract

All endpoints require a Bearer token (reuse `get_current_user`). JSON is camelCase. Timestamps are ISO 8601 in UTC.

### 5.1 Endpoints

| Method and path | Purpose | Success |
|---|---|---|
| `POST /projects` | Create a workspace | `201` + project |
| `GET /projects` | List my projects (search, filter, sort, paginate) | `200` + page |
| `GET /projects/{id}` | Workspace overview | `200` + overview |
| `PATCH /projects/{id}` | Partial update (title, researchField, abstract, keywords, status) | `200` + project |
| `DELETE /projects/{id}` | Delete project, its shortlist rows, its file | `204` |
| `PUT /projects/{id}/target-journal/{journalId}` | Set the target journal (also shortlists it) | `200` + overview |
| `DELETE /projects/{id}/target-journal` | Clear the target journal (stays shortlisted) | `200` + overview |
| `POST /projects/{id}/manuscript` | Upload or replace the draft file (multipart) | `201` + manuscript info |
| `DELETE /projects/{id}/manuscript` | Remove the draft file now | `204` |
| `GET /projects/{id}/activity` | Activity for one project | `200` + items |
| `GET /activity/recent` | Recent activity across my projects (dashboard feed) | `200` + items |

**Superseding the Finder plan:** if the Finder plan already created `PUT /projects/{id}`, replace it with `PATCH` (the finder page only calls create and shortlist, so nothing breaks; confirm by searching the frontend). Add `"PATCH"` to `allow_methods` in `backend/app/main.py` CORS middleware, and mount the new activity router at both root and `/api` (matching `projects_router` and `journals_router`). The shortlist endpoints from the Finder plan stay as they are, with two small additions: they write activity rows and bump `projects.updated_at` (and `DELETE /projects/{id}/shortlist/{journalId}` must clear `is_selected` or delete the row so `CHECK (NOT is_selected OR is_shortlisted)` is never violated).

### 5.2 Request and response shapes

**Create** `POST /projects`
```json
{ "title": "Federated learning for seismic interpretation",
  "researchField": "Machine learning",
  "abstract": "optional text",
  "keywords": ["federated learning", "seismic"] }
```
Only `title` is required. `status` in the body is ignored (new projects are always `draft`).

**Project object**
```json
{ "id": "12",
  "title": "...",
  "researchField": "Machine learning",
  "abstract": null,
  "keywords": [],
  "status": "draft",
  "createdAt": "2026-11-09T10:15:00Z",
  "updatedAt": "2026-11-09T10:15:00Z",
  "manuscript": null }
```

**Manuscript object** (inside the project object when a file is attached or was purged)
```json
{ "fileName": "draft_v3.docx", "sizeBytes": 183422,
  "uploadedAt": "2026-11-09T10:20:00Z",
  "available": true,
  "expiresAt": "2026-11-09T12:20:00Z" }
```
`available` is false if the file was purged or is missing on disk. The server path is **never** returned.

**List** `GET /projects?search=&status=&sort=updatedAt&order=desc&page=1&pageSize=20`
```json
{ "items": [ { "id": "12", "title": "...", "researchField": "...", "status": "draft",
               "createdAt": "...", "updatedAt": "...",
               "shortlistedCount": 3, "hasManuscript": true,
               "targetJournalTitle": null } ],
  "total": 37, "page": 1, "pageSize": 20 }
```
List items are light: no abstract, no activity. `sort` is one of `updatedAt`, `createdAt`, `title`. `pageSize` 1 to 100 (default 20). Order ties are broken by `id` so pages are stable.

**Overview** `GET /projects/{id}` = project object plus:
```json
{ "shortlistedCount": 3,
  "targetJournal": { "id": "7", "title": "...", "publisher": "..." },
  "counts": { "conversions": 0, "complianceReports": 0 },
  "recentActivity": [ { "id": "88", "eventType": "project_created", "createdAt": "...", "details": {} } ] }
```
`recentActivity` holds the latest 5 events.

**Activity item** (both activity endpoints)
```json
{ "id": "88", "projectId": "12", "projectTitle": "...", "eventType": "journal_shortlisted",
  "details": { "journalId": 7 }, "journalTitle": "IEEE Transactions on Image Processing",
  "createdAt": "..." }
```
`journalTitle` is resolved at read time from the catalog (catalog data is public). `projectId` is null if the project was deleted. Cursor pagination: `limit` (1 to 50, default 20) and `before` (an activity id).

### 5.3 Errors

| Status | When | Message style |
|---|---|---|
| 401 | Missing, invalid or expired token | "Not authenticated" |
| 404 | Unknown project or journal, or someone else's project | "Project not found" (identical body in both cases) |
| 409 | Project limit reached | "Project limit reached" |
| 413 | Upload larger than the limit | "File is too large (maximum 20 MB)" |
| 415 | Unsupported or mismatched file type | "Unsupported file type" |
| 422 | Validation failure (blank title, bad page size, invalid ID format, empty PATCH body, empty file) | Field-specific message the UI can show inline |
| 500 | Unexpected | Generic message. Never a stack trace or a file path |

---

## 6. Implementation plan

The plan has two parts. **Part A** delivers the core workspace (everything in the report's Use Case 4.3 plus the dashboard). **Part B** adds the draft file and the target journal. Run Part A completely, check it works end to end, then do Part B.

### Hard rules for the agent (paste at the top of every session)

1. Work on a new branch `feature/workspace`. Commit backend and frontend separately.
2. Frontend edits are allowed **only** to the files approved in Phase W1. No restyling, no layout or copy changes beyond what this plan lists, no other pages.
3. Every schema change goes through an Alembic migration shown for review before it is applied.
4. Never log or store abstract text, manuscript content or file names in logs or in `activity_logs.details`.
5. Never use a client-supplied file name as a path on disk. Never return an absolute server path.
6. Never expose another user's data. Unknown and foreign IDs return the same `404`.
7. Work one phase at a time and stop where the plan says STOP.

---

### PART A: Workspace core

#### Phase W1: Pre-flight, reconciliation and frontend recon (STOP and report)

1. Check that auth works (`get_current_user`), the database is migrated, and `pytest -q` is green.
2. **Reconcile with the Finder plan.** Report the state of each item below, then act as the table says:

| Item | If it already exists | If it does not |
|---|---|---|
| `projects.keywords` | Keep | Add it in this plan's migration |
| `project_journals.is_shortlisted` | Keep | Add it in this plan's migration |
| `POST/GET/GET one/PUT/DELETE /projects` | Extend and move into the structure below; replace `PUT` with `PATCH` | Create all of it here |
| Shortlist endpoints | Keep; add activity logging and `updated_at` bump | Not needed here (Finder plan Phase 8 owns them); do the target journal endpoints only |

3. **Read-only frontend recon.** Report:
   - the `Project` type and the exact status labels the status pills use;
   - the Projects/Workspace Manager page, the New Project modal (if it exists), the workspace overview page (if it exists), and the Dashboard (project cards and the activity feed);
   - how `AppContext` holds `projects` and `activeProject` and everything that reads them (including the Finder page);
   - the API helper from the auth work, any notification (toast) component, and any confirm-dialog component;
   - where the manuscript upload area would live.
4. Propose the exact list of frontend files to change. Wait for approval.

#### Phase W2: Migration

Implement Section 4 exactly. Show the migration, wait for approval, apply it, and verify:
- upgrade on a database that already has projects backfills `status = 'draft'` and `updated_at = created_at`;
- `downgrade -1` then `upgrade head` both work;
- the new CHECK constraints and indexes exist (`\d projects`, `\d activity_logs`, `\d project_journals` in psql).

Update the SQLAlchemy models and the schema tests.

#### Phase W3: Settings and services

1. Settings (add to `.env.example`): `MAX_PROJECTS_PER_USER=50`, `MAX_UPLOAD_MB=20`, `STORAGE_ROOT=./storage/workspaces`, `WORKSPACE_FILE_TTL_MINUTES=120`, `CLEANUP_INTERVAL_MINUTES=10`. Add `storage/` to `backend/.gitignore`.
2. `app/services/activity.py`: `log_activity(db, user_id, project, event_type, details)`. It writes inside the **caller's transaction** (if the main action rolls back, the log row rolls back too). It enforces the details whitelist per event type and fills the title snapshot.
3. `app/services/projects.py`: one place for ownership checks (`get_owned_project_or_404(db, user, project_id)`), normalization (below) and the project cap check.
4. Normalization rules (one shared module, unit tested):
   - `title`: trim, collapse runs of whitespace to one space, 1 to 300 characters, reject control characters and NUL.
   - `researchField`: trim; empty becomes null; at most 150 characters.
   - `abstract`: at most 10,000 characters; empty becomes null.
   - `keywords`: accept a list or a comma-separated string; trim each, drop empties, remove duplicates ignoring case (keep first spelling), at most 20 items, each at most 60 characters.
   - `status`: must be in the allowed set.
   - Unknown request fields are ignored (never applied).

#### Phase W4: Project endpoints

Implement create, list, overview, patch and delete (Section 5).

- **Create:** the project cap check must be race-safe: lock the user row (`SELECT ... FOR UPDATE`) while counting and inserting, so ten parallel requests cannot exceed the cap. Log `project_created`.
- **List:** one query with grouped counts (shortlisted count, has manuscript, target journal title). It must **not** run one query per project. Search is case-insensitive partial matching on title and research field. Escape `%`, `_` and `\` in the search text so they are matched literally. Validate `sort`, `order`, `page` and `pageSize`.
- **Overview:** project, counts, target journal, last 5 activity events. If the database says a file is present but it is missing on disk, report `available: false` and heal the row (set `file_deleted_at`, clear the path).
- **Patch:** apply only the fields present in the request (`model_fields_set`); an explicit `null` clears nullable fields. An empty body returns `422`. If nothing actually changed, do not bump `updated_at` and do not log. Log `project_updated` (field **names** only) and `project_status_changed` (from and to).
- **Delete:** delete the project row (cascades through shortlist rows, jobs, reports, issues), commit, then delete the project's storage folder on a best-effort basis (a leftover folder is cleaned by the orphan sweep in Phase W11). Log `project_deleted` with the title snapshot (the row's `project_id` becomes null by the foreign key).
- **Shortlist reconciliation & CORS:** in `DELETE /projects/{id}/shortlist/{journal_id}`, ensure unshortlisting a selected journal also clears `is_selected` (or deletes the row) so the Phase W2 `CHECK (NOT is_selected OR is_shortlisted)` constraint is satisfied immediately in Part A. Add `"PATCH"` to `allow_methods` in `backend/app/main.py`.
- `updated_at` is bumped by user actions on the project (patch, upload, remove file, target journal, shortlist changes). It is **not** bumped by background purge.

#### Phase W5: Activity endpoints

`GET /projects/{id}/activity` and `GET /activity/recent`, newest first, cursor pagination, owner-scoped. Mount the activity router at both root and `/api` in `backend/app/main.py`. Resolve `journalTitle` for journal events with one batched lookup (no per-row queries).

#### Phase W6: Backend tests for Part A (STOP)

Write the tests from the Section 8 groups: DB, VAL, ACT, CRE, LST, GET, UPD, DEL, LOG, SEC (Part A items) and PERF (Part A items). Update existing tests in `backend/tests/test_projects.py` from the Finder plan so they match the superseded contract (`PATCH` instead of `PUT`, paginated `GET /projects`, `204` on `DELETE`). Show the results and show the endpoints working in the interactive API docs page.

#### Phase W7: Frontend wiring for Part A

Only the approved files. Follow Section 7 for details. Summary:
1. API functions: `createProject`, `listProjects`, `getProject`, `updateProject`, `deleteProject`, `getRecentActivity`, `getProjectActivity` (reuse the existing `apiRequest` helper in `frontend/src/lib/api.ts`, updating it to return cleanly on `204 No Content` and to omit `'Content-Type': 'application/json'` when sending `FormData`). Update `Project` types in `frontend/src/types/index.ts` (keeping `field` mapped to `researchField` so existing card bindings work seamlessly).
2. `AppContext`: replace mock projects with API data; add `activeProject` persistence and clearing on logout.
3. Projects page: list with loading, empty, error and populated states; search, status filter, sort, pagination.
4. New Project modal (in both `ProjectsPage.tsx` and `DashboardPage.tsx`): title (required) and research field (optional); blank title shows an inline prompt (report alternative flow 3-A); success notification; the new project appears in the list.
5. Workspace overview page: if no workspace overview page exists, create one at `/projects/:id` (`frontend/src/pages/WorkspaceOverviewPage.tsx`) using existing components and styles only, and add the router file (`App.tsx`, `TopBar.tsx`) and the new page to the approved file list in Phase W1 for review before editing. If a page or panel already exists, wire it to the API instead and do not create a second route. Load by ID, show details, status, shortlist count, activity, rename/edit controls, and delete with confirmation.
6. Dashboard: project cards and recent activity feed from the API.
7. No other pages change. Pages that still use mock data (Compare, Guidelines, etc.) must keep working.

#### Phase W8: Part A verification (STOP)

Run the Section 9 E2E checklist items for Part A. Confirm `npm run build` passes and `git diff --stat main -- frontend/` lists only approved files.

---

### PART B: Manuscript attachment and target journal

#### Phase W9: Target journal endpoints

- `PUT /projects/{id}/target-journal/{journalId}`: in one transaction, set `is_selected = true` and `is_shortlisted = true` for that journal and clear `is_selected` on any other journal in the project. The unique index must not fail under concurrent requests (lock the project row first). Log `target_journal_set`.
- `DELETE /projects/{id}/target-journal`: clears `is_selected` (the journal stays shortlisted). Log `target_journal_cleared`.
- Update the Finder plan's unshortlist endpoint: unshortlisting the target journal also clears the target (the CHECK constraint forbids selected-but-not-shortlisted). Log both events.

#### Phase W10: Storage service and upload endpoints

`app/services/storage.py`:
1. Root from `STORAGE_ROOT`; one folder per project: `<root>/<project_id>/`. Create folders with owner-only permissions (0700 on Linux).
2. Stored file name = `uuid4().hex` + lowercase extension. The original name is kept only as sanitized display metadata (strip path parts, control characters, limit to 255 characters).
3. A path guard: every resolved path must stay inside the root, or the operation raises an error. Never follow symlinks outside the root.
4. Atomic write: write to a temporary name in the same folder, then `os.replace` into the final name. A crash must never leave a half-written final file.
5. Idempotent delete: deleting a missing file is not an error.

`POST /projects/{id}/manuscript`:
1. Dependency: add `python-multipart` to `requirements.txt`.
2. Accept exactly one file field. Extension must be `.docx`, `.tex` or `.pdf` (case-insensitive). Reject everything else with `415`. Legacy `.doc` is rejected with a hint to save as `.docx`.
3. **Stream** the upload in chunks and abort as soon as the size passes the limit (`413`). Never load the whole file into memory. Reject empty files (`422`). Do not trust the `Content-Length` header or the client's MIME type.
4. **Content check (sniffing)** after the size check:
   - `.docx`: must be a valid zip containing `[Content_Types].xml` and `word/document.xml`; reject if it contains a macro project (`vbaProject.bin`); reject zip bombs (too many entries, or total uncompressed size or compression ratio above a safe limit), by reading the zip directory without extracting.
   - `.pdf`: must start with `%PDF-` within the first 1,024 bytes.
   - `.tex`: must decode as text and contain no NUL bytes.
5. **Replace safely:** write the new file first, then update the database row, then delete the old file. If the database update fails, delete the new file and leave the old state untouched.
6. Set `manuscript_filename`, `manuscript_size_bytes`, `manuscript_uploaded_at`, `current_file_path`, clear `file_deleted_at`, bump `updated_at`, log `manuscript_uploaded` (`extension`, `sizeBytes`, `replaced`).
7. Return the manuscript object (no server path).

`DELETE /projects/{id}/manuscript`: delete the file, null the path and metadata, set `file_deleted_at`, log `manuscript_removed`. If there is no file, return `404` "No manuscript attached".

#### Phase W11: Automatic cleanup

`app/tasks/cleanup.py`, started from the FastAPI lifespan handler (run the blocking work in a worker thread so the server stays responsive):

1. **Expired files:** every `CLEANUP_INTERVAL_MINUTES`, find projects whose `manuscript_uploaded_at` is older than the TTL and whose file is still present. For each: delete the file, null `current_file_path`, set `file_deleted_at`, log `manuscript_purged`. Do not bump `updated_at`. Use `SELECT ... FOR UPDATE SKIP LOCKED` so several server workers can run the job without clashing.
2. **Orphan sweep:** delete files and folders under `STORAGE_ROOT` that no project references **and** are older than the TTL (covers crashes and the best-effort delete in Phase W4). Files younger than the TTL are left alone (an upload may be in progress).
3. **Run once at startup**, then on the interval.
4. One failure must not stop the others: catch, log the project ID (not names), and continue.
5. Inject the clock (a function parameter) so tests can simulate time without sleeping.
6. Refuse to delete anything whose resolved path is outside the root, even if the database contains such a path.

#### Phase W12: Backend tests for Part B (STOP)

Tests: TGT, UPL, MDL, PRG, and the remaining SEC, PERF and INT items. Show results.

#### Phase W13: Frontend wiring for Part B

1. API functions: `uploadManuscript` (with progress if the helper supports it), `deleteManuscript`, `setTargetJournal`, `clearTargetJournal`.
2. Workspace overview: the draft file card with states (none, uploaded with expiry time, expired), upload with progress, replace, remove, and the messages in Section 7.3.
3. Show the target journal on the overview and let the user set or clear it from the shortlist if a control exists. Do not invent new controls.
4. Add a short privacy note on the upload area, for example "Files are deleted automatically after 2 hours", using the existing text style.

#### Phase W14: Final verification and documentation

Run the whole Section 9 checklist. Update `backend/README.md`: endpoints, settings, storage and cleanup behaviour, the deviations (new columns, `activity_logs` as **D8**, the shortlist-implies-selected CHECK), and known limitations.

---

## 7. Frontend integration details

### 7.1 State
- `projects` come from the API after login; `isProjectsLoading` and an error flag are exposed by the context.
- `activeProject` is a project the user has opened or just created. Store only its **ID** in `localStorage` under one key, and validate it with `GET /projects/{id}` on app load. If it returns `404`, clear it silently.
- **On logout, clear `projects`, `activeProject` and the stored ID.** A second user on the same browser must never see the first user's data, not even for a moment.
- The URL (`/projects/:id`) is the source of truth on the overview page; the context only mirrors it.

### 7.2 List, modal and delete
- **Empty state** when the user has no projects, with the New Project button.
- **Loading** uses skeletons or the existing loading style. **Error** shows a retry.
- **Search** is debounced (about 300 ms) and resets to page 1. Filters and sort are sent as query parameters.
- **Modal:** the submit button is disabled while the request is running (prevents duplicate projects), Esc and Cancel close it without creating anything, server errors are shown inline, a blank title shows the prompt from the report's alternative flow. Focus moves into the modal on open and back to the New Project button on close.
- **Delete:** a confirmation that says the project's shortlist, results and attached file will be deleted. After success it is removed from the list; if the deleted project was the active one, clear it.
- All text from the user (titles, fields) is rendered as plain text. No raw HTML injection anywhere.
- Long titles are truncated with an ellipsis and never break the layout. Unicode and right-to-left text display correctly.

### 7.3 Upload area messages
| Situation | Message |
|---|---|
| Wrong type | "Unsupported file type. Use .docx, .tex or .pdf." |
| Legacy .doc | "Please save the file as .docx and try again." |
| Too large | "File is too large (maximum 20 MB)." |
| Empty file | "This file is empty." |
| Content does not match type | "This file looks damaged or is not a valid <type> file." |
| Upload failed (network) | "Upload failed. Check your connection and try again." |
| Expired file | "Your file was removed automatically for privacy. Upload it again to continue." |

### 7.4 Do not
- Do not change layout, colors or unrelated copy.
- Do not wire the Compare, Guidelines, Conversion or Compliance pages (later plans).
- Do not add status transitions logic beyond a plain status selector, if one exists.

---

## 8. Test catalog

Notation: **ID | scenario | expected result.** "A" = Part A, "B" = Part B. Use `pytest` with the FastAPI test client against the test database; `tmp_path` for the storage root; an injected clock for time-based tests; two or more test users (A, B) for ownership tests. Mark slow tests with `@pytest.mark.slow`.

### 8.1 Database and migration (A)

| ID | Scenario | Expected |
|---|---|---|
| WS-DB-01 | Upgrade on a clean database | Succeeds; all new columns, table, constraints, indexes exist |
| WS-DB-02 | Upgrade on a database with existing projects | `status = 'draft'`, `updated_at = created_at` for old rows; no data lost |
| WS-DB-03 | Downgrade one step, then upgrade | Both succeed; schema identical after the round trip |
| WS-DB-04 | Insert project with empty or whitespace-only title | Rejected by the CHECK constraint |
| WS-DB-05 | Insert project with title of 301 characters | Rejected |
| WS-DB-06 | Insert status `bogus` | Rejected by CHECK |
| WS-DB-07 | Insert negative `manuscript_size_bytes` | Rejected |
| WS-DB-08 | Insert `activity_logs.details` as a JSON array | Rejected by CHECK |
| WS-DB-09 | Delete a user | Their projects and activity rows are deleted |
| WS-DB-10 | Delete a project that has activity rows | Rows stay with `project_id` null and the title snapshot intact |
| WS-DB-11 | Delete a project that has shortlist rows, jobs, reports | All children deleted (cascade) |
| WS-DB-12 | Set `is_selected = true, is_shortlisted = false` | Rejected by the CHECK |
| WS-DB-13 | Two selected journals in one project | Rejected by the partial unique index |
| WS-DB-14 | Update a project through the ORM | `updated_at` changes |
| WS-DB-15 | Indexes `(user_id, updated_at)` and `(user_id, status)` exist | Present |
| WS-DB-16 | Backfill: existing selected rows get `is_shortlisted = true` before the CHECK is added | Migration succeeds with such rows |

### 8.2 Validation and unit tests (A)

| ID | Scenario | Expected |
|---|---|---|
| WS-VAL-01 | Title with leading and trailing spaces | Trimmed |
| WS-VAL-02 | Title with runs of inner spaces and tabs | Collapsed to single spaces |
| WS-VAL-03 | Title of only spaces, or empty | Rejected |
| WS-VAL-04 | Title with 300 characters / 301 characters | Accepted / rejected |
| WS-VAL-05 | Title in Urdu, Arabic, Chinese, with emoji | Accepted and returned unchanged |
| WS-VAL-06 | Title containing `<script>alert(1)</script>` | Stored as plain text, not rejected |
| WS-VAL-07 | Title with NUL or control characters | Rejected |
| WS-VAL-08 | `researchField` empty string | Stored as null |
| WS-VAL-09 | `researchField` of 150 / 151 characters | Accepted / rejected |
| WS-VAL-10 | Keywords with duplicates in different case, blanks, padding | Deduplicated, trimmed, blanks dropped, first spelling kept |
| WS-VAL-11 | Keywords as a comma-separated string | Split into a list |
| WS-VAL-12 | 20 keywords / 21 keywords | Accepted / rejected |
| WS-VAL-13 | A keyword of 60 / 61 characters | Accepted / rejected |
| WS-VAL-14 | Abstract of 10,000 / 10,001 characters | Accepted / rejected |
| WS-VAL-15 | Status outside the allowed set | Rejected |
| WS-VAL-16 | Body includes `id`, `userId`, `createdAt`, `manuscript`, `status` on create | Ignored, never applied |
| WS-VAL-17 | Search text containing `%`, `_`, `\` | Escaped; matched literally |

### 8.3 Activity service (A)

| ID | Scenario | Expected |
|---|---|---|
| WS-ACT-01 | Action succeeds | Exactly one activity row in the same transaction |
| WS-ACT-02 | Action fails and rolls back | No activity row |
| WS-ACT-03 | Event `details` contains a non-whitelisted key (e.g. abstract) | Dropped or rejected; never stored |
| WS-ACT-04 | Title snapshot | Equals the title at event time even after a later rename |
| WS-ACT-05 | Unknown event type | Rejected in code |

### 8.4 Create project (A)

| ID | Scenario | Expected |
|---|---|---|
| WS-CRE-01 | Valid body with only `title` | `201`; status `draft`; `keywords` is `[]`; `id` is a string; both timestamps present |
| WS-CRE-02 | Full valid body | Stored with normalization applied |
| WS-CRE-03 | Missing title | `422` |
| WS-CRE-04 | Empty or whitespace title | `422` with a message the UI can show |
| WS-CRE-05 | Title longer than 300 | `422` |
| WS-CRE-06 | No token / garbage token / expired token | `401` |
| WS-CRE-07 | Token for a deleted user | `401` |
| WS-CRE-08 | Body contains `userId` of another user | Ignored; project belongs to the token's user |
| WS-CRE-09 | Body contains `status: "submitted"` | Ignored; project is `draft` |
| WS-CRE-10 | Two requests with identical titles | Both created with different IDs |
| WS-CRE-11 | User at the project cap creates another | `409`; another user is unaffected |
| WS-CRE-12 | 10 parallel creates when the user has 45 projects | Total never exceeds 50 |
| WS-CRE-13 | Database error during insert | `500` generic; no project row, no activity row |
| WS-CRE-14 | Response keys | camelCase only; no `user_id`, no snake_case |
| WS-CRE-15 | Malformed JSON | `422` (or `400`), not `500` |
| WS-CRE-16 | Wrong content type (form data) | `415` or `422`, not `500` |
| WS-CRE-17 | Abstract of 1 MB | `422` or `413`, not `500` |
| WS-CRE-18 | SQL injection text in title and field (`'; DROP TABLE projects; --`) | Stored literally; tables intact |
| WS-CRE-19 | Success creates `project_created` activity | One row, correct title snapshot |
| WS-CRE-20 | Project appears in the owner's list immediately | Yes |

### 8.5 List projects (A)

| ID | Scenario | Expected |
|---|---|---|
| WS-LST-01 | User with no projects | `items: []`, `total: 0` |
| WS-LST-02 | Two users each with projects | Each sees only their own |
| WS-LST-03 | Default ordering | `updatedAt` descending |
| WS-LST-04 | `sort=title`, `sort=createdAt`, both orders | Correct ordering |
| WS-LST-05 | Invalid `sort` or `order` value | `422` |
| WS-LST-06 | `page=2&pageSize=10` with 25 projects | Items 11 to 20; `total` 25 |
| WS-LST-07 | Page beyond the last | Empty items; correct `total` |
| WS-LST-08 | `page=0`, `pageSize=0`, `pageSize=101`, negative values, non-numeric | `422` |
| WS-LST-09 | Search "seismic" matches "Seismic Analysis" | Match is case-insensitive and partial |
| WS-LST-10 | Search for `100%` and `a_b` | Treated literally, not as wildcards |
| WS-LST-11 | Search with only spaces, or empty | No filter applied |
| WS-LST-12 | Search matches the research field | Included |
| WS-LST-13 | Search with Unicode text | Works |
| WS-LST-14 | `status=draft` / invalid status | Filtered / `422` |
| WS-LST-15 | Search plus status plus sort plus page together | Combined correctly |
| WS-LST-16 | Many projects with identical `updatedAt` | Stable order across pages (tie-break by id), no duplicates or gaps |
| WS-LST-17 | `shortlistedCount`, `hasManuscript`, `targetJournalTitle` | Match the data |
| WS-LST-18 | List payload | Contains no abstract text |
| WS-LST-19 | Number of SQL statements for 1 project vs 50 projects | Same (no N+1) |
| WS-LST-20 | No token | `401` |

### 8.6 Get overview (A)

| ID | Scenario | Expected |
|---|---|---|
| WS-GET-01 | Own project | `200` with project, counts, target journal, up to 5 activity items |
| WS-GET-02 | Another user's project | `404` with the same body as a nonexistent project |
| WS-GET-03 | Nonexistent ID | `404` |
| WS-GET-04 | ID `abc` | `422` |
| WS-GET-05 | ID `0`, negative, or larger than the integer range | `404` or `422`, never `500` |
| WS-GET-06 | Project without a file | `manuscript` is null |
| WS-GET-07 | File purged | `manuscript.available` is false |
| WS-GET-08 | Target journal set | Appears with id, title, publisher |
| WS-GET-09 | `recentActivity` | At most 5, newest first |
| WS-GET-10 | Counts | `shortlistedCount` correct; `conversions` and `complianceReports` are 0 for now |
| WS-GET-11 | Database says file present but it is missing on disk | `available: false` and the row is healed |
| WS-GET-12 | Deleted project | `404` |

### 8.7 Update project (A)

| ID | Scenario | Expected |
|---|---|---|
| WS-UPD-01 | Change title | `200`; `updatedAt` increases; activity `project_updated` with field names only |
| WS-UPD-02 | Send only `researchField` | Other fields unchanged |
| WS-UPD-03 | Empty body `{}` | `422` |
| WS-UPD-04 | Invalid title | `422`; nothing changed |
| WS-UPD-05 | `abstract: null` | Abstract cleared |
| WS-UPD-06 | `keywords: []` | Keywords cleared |
| WS-UPD-07 | Valid status change | `200`; `project_status_changed` logged with from and to |
| WS-UPD-08 | Invalid status | `422` |
| WS-UPD-09 | Another user's project | `404`; nothing changed |
| WS-UPD-10 | Body tries to set `id`, `userId`, `createdAt`, manuscript fields | Ignored |
| WS-UPD-11 | Send the same values as the current ones | `200`; no `updatedAt` bump; no activity row |
| WS-UPD-12 | Two concurrent patches to different fields | Both succeed; no `500`; final state is consistent |
| WS-UPD-13 | Patch after the project was deleted | `404` |
| WS-UPD-14 | Abstract contents never appear in the activity row | Confirmed |

### 8.8 Delete project (A, with B checks marked)

| ID | Scenario | Expected |
|---|---|---|
| WS-DEL-01 | Delete own project | `204`; later `GET` returns `404` |
| WS-DEL-02 | Project with shortlist rows, jobs, reports, issues | All removed |
| WS-DEL-03 | (B) Project with an attached file | File and the project folder removed from disk |
| WS-DEL-04 | (B) File removal fails (simulated) | Still `204`; error logged; orphan sweep removes it later |
| WS-DEL-05 | Another user's project | `404`; nothing deleted |
| WS-DEL-06 | Delete twice | Second returns `404` |
| WS-DEL-07 | Activity | `project_deleted` row exists with title snapshot and null `projectId` |
| WS-DEL-08 | Other projects of the same user | Untouched |
| WS-DEL-09 | (B) Delete while an upload is in progress | No orphan remains after the next sweep; no `500` |
| WS-DEL-10 | No token | `401` |

### 8.9 Activity endpoints (A)

| ID | Scenario | Expected |
|---|---|---|
| WS-LOG-01 | Project feed | Newest first, only that project |
| WS-LOG-02 | `limit` and `before` cursor | Correct pages; no duplicates or gaps |
| WS-LOG-03 | `limit=0` or `limit=51` | `422` |
| WS-LOG-04 | Another user's project feed | `404` |
| WS-LOG-05 | `/activity/recent` | Only the user's events across projects, newest first |
| WS-LOG-06 | Events of a deleted project | Still listed with null `projectId` and the snapshot title |
| WS-LOG-07 | Journal events | `journalTitle` resolved with a constant number of queries |
| WS-LOG-08 | No sensitive content in `details` | Confirmed by scanning all event types |
| WS-LOG-09 | No token | `401` |

### 8.10 Target journal (B)

| ID | Scenario | Expected |
|---|---|---|
| WS-TGT-01 | Set target on a shortlisted journal | `is_selected` and `is_shortlisted` true; shown in overview and list |
| WS-TGT-02 | Set target on a journal not yet shortlisted | It becomes shortlisted and selected |
| WS-TGT-03 | Change target from journal 1 to journal 2 | Exactly one selected; journal 1 still shortlisted |
| WS-TGT-04 | Set the same target twice | Idempotent `200` |
| WS-TGT-05 | Unknown journal | `404` |
| WS-TGT-06 | Another user's project | `404` |
| WS-TGT-07 | Clear target | Not selected; still shortlisted |
| WS-TGT-08 | Clear when none is set | `200`, no error |
| WS-TGT-09 | Two simultaneous requests selecting different journals | Exactly one wins; no `500`; invariant holds |
| WS-TGT-10 | Unshortlist the target journal via the Finder endpoint | Target is cleared too; two activity events |
| WS-TGT-11 | Activity events | `target_journal_set` and `target_journal_cleared` with `journalId` only |
| WS-TGT-12 | `updatedAt` | Bumped on set and clear |

### 8.11 Upload manuscript (B)

| ID | Scenario | Expected |
|---|---|---|
| WS-UPL-01 | Valid `.docx` | `201`; metadata correct; file exists under the project folder with a UUID name; DB fields set; activity logged |
| WS-UPL-02 | Valid `.pdf` | Same |
| WS-UPL-03 | Valid `.tex` | Same |
| WS-UPL-04 | `.exe`, `.zip`, `.png`, `.html`, `.docm` | `415` |
| WS-UPL-05 | Legacy `.doc` | `415` with the "save as .docx" hint |
| WS-UPL-06 | Text file renamed to `.docx` | `415` (content check) |
| WS-UPL-07 | Text file renamed to `.pdf` | `415` |
| WS-UPL-08 | Binary file renamed to `.tex` (contains NUL bytes) | `415` |
| WS-UPL-09 | `.docx` containing `vbaProject.bin` | `415` |
| WS-UPL-10 | Zip bomb disguised as `.docx` (huge uncompressed size or ratio) | Rejected; nothing extracted to disk |
| WS-UPL-11 | Empty file | `422` |
| WS-UPL-12 | File of exactly 20 MB | Accepted |
| WS-UPL-13 | File of 20 MB plus 1 byte | `413`; no partial file left on disk |
| WS-UPL-14 | Streamed or chunked upload with a false small `Content-Length` | Aborted at the real limit |
| WS-UPL-15 | No file field | `422` |
| WS-UPL-16 | Two files in one request | `422` |
| WS-UPL-17 | Upload when a file already exists | Old file deleted, new file in place, `uploadedAt` updated, `replaced: true` in the event |
| WS-UPL-18 | Database failure after the new file is written | New file removed; old file and old metadata intact |
| WS-UPL-19 | File name `../../etc/passwd.docx` | Stored under a UUID inside the project folder; display name sanitized |
| WS-UPL-20 | Names with Unicode (Urdu), emoji, spaces, 300 characters, no extension, `paper.pdf.exe`, uppercase `.DOCX` | Handled safely: uppercase accepted, double extension and no extension rejected, long names truncated for display |
| WS-UPL-21 | Same file name uploaded to two projects | No collision |
| WS-UPL-22 | Another user's project | `404`; nothing written to disk |
| WS-UPL-23 | No token | `401` |
| WS-UPL-24 | Two concurrent uploads to the same project | Final state consistent: one file referenced, the other deleted |
| WS-UPL-25 | Simulated disk-full or write error | Generic `500` (or `507`); DB unchanged; no partial file |
| WS-UPL-26 | Response body | No server path anywhere |
| WS-UPL-27 | Wrong MIME type header but correct content | Judged by content, accepted |
| WS-UPL-28 | `expiresAt` | Equals `uploadedAt` plus the TTL |
| WS-UPL-29 | `updatedAt` | Bumped |
| WS-UPL-30 | Memory use while uploading 20 MB | Stays flat (streaming) |

### 8.12 Remove manuscript (B)

| ID | Scenario | Expected |
|---|---|---|
| WS-MDL-01 | Remove existing file | `204`; file gone; metadata nulled; `file_deleted_at` set; `manuscript_removed` logged |
| WS-MDL-02 | Remove when none attached | `404` "No manuscript attached" |
| WS-MDL-03 | File already missing on disk | `204`; row cleaned |
| WS-MDL-04 | Another user's project | `404` |
| WS-MDL-05 | Re-upload after removal | Works; `file_deleted_at` cleared |

### 8.13 Automatic cleanup (B)

| ID | Scenario | Expected |
|---|---|---|
| WS-PRG-01 | File older than the TTL | Deleted; path nulled; `file_deleted_at` set; `manuscript_purged` logged |
| WS-PRG-02 | File younger than the TTL | Kept |
| WS-PRG-03 | File exactly at the TTL boundary | Behaviour matches the documented rule (purge at age greater than or equal to TTL) |
| WS-PRG-04 | Run the job twice | Second run changes nothing; no errors |
| WS-PRG-05 | `updated_at` after purge | Unchanged |
| WS-PRG-06 | Overview after purge | `available: false`; frontend shows the expired message |
| WS-PRG-07 | DB says present, file missing | Row healed without error |
| WS-PRG-08 | Orphan file on disk older than the TTL | Removed |
| WS-PRG-09 | Orphan file younger than the TTL (upload in progress) | Kept |
| WS-PRG-10 | Folder for a deleted project | Removed |
| WS-PRG-11 | One file fails to delete | Others still processed; error logged with project ID only |
| WS-PRG-12 | Job runs at startup | Leftovers from a crash are cleaned |
| WS-PRG-13 | Two workers run the job at once | No double processing, no errors (`SKIP LOCKED`) |
| WS-PRG-14 | DB contains a path pointing outside the root | Refused; nothing outside the root is deleted; logged |
| WS-PRG-15 | TTL changed in settings | New value respected |
| WS-PRG-16 | Cleanup does not block API requests | Confirmed (runs in a worker thread) |

### 8.14 Security (A and B)

| ID | Scenario | Expected |
|---|---|---|
| WS-SEC-01 | **Ownership matrix:** call every endpoint in Section 5 with user B's token on user A's project | Always `404`; no data returned; no change made |
| WS-SEC-02 | Same endpoints with no token | `401` |
| WS-SEC-03 | Unknown vs foreign project ID | Identical status and body |
| WS-SEC-04 | Mass assignment on create and patch | Protected fields ignored |
| WS-SEC-05 | XSS payloads in title, field, keywords, file name | Stored as text; rendered escaped in the UI |
| WS-SEC-06 | SQL injection in search, sort, ids | No effect; sort accepts only known values |
| WS-SEC-07 | Path traversal in upload file name | Never used for disk paths |
| WS-SEC-08 | Uploaded files are not served statically | No route or mount exposes `STORAGE_ROOT` |
| WS-SEC-09 | Error responses | No stack trace, no file path, no SQL |
| WS-SEC-10 | Logs for create, upload, delete, purge | Contain IDs only: no titles, abstracts, file names, tokens |
| WS-SEC-11 | CORS | Only the configured frontend origin is allowed |
| WS-SEC-12 | Very large headers or bodies | Rejected cleanly |
| WS-SEC-13 | Timing and response of foreign IDs | No obvious difference from nonexistent IDs |
| WS-SEC-14 | Storage folder permissions (Linux) | Owner-only |
| WS-SEC-15 | Symlink inside the storage root pointing outside | Never followed |

### 8.15 Performance (A and B)

| ID | Scenario | Expected |
|---|---|---|
| WS-PERF-01 | List with 1,000 projects, first page | Responds quickly (target: well under 300 ms locally) |
| WS-PERF-02 | List and overview statement counts | Constant, independent of the number of projects |
| WS-PERF-03 | 20 parallel creates by different users | All succeed |
| WS-PERF-04 | Upload of 20 MB | Completes in reasonable time with flat memory |
| WS-PERF-05 | Purge of 1,000 expired files | Completes within the interval |
| WS-PERF-06 | Activity feed with 10,000 rows for one user | First page is fast (index used) |

### 8.16 Integration with the Finder (A and B)

| ID | Scenario | Expected |
|---|---|---|
| WS-INT-01 | Finder auto-creates a project on first shortlist | Project appears in the list with status `draft` and the search keywords |
| WS-INT-02 | Shortlist a journal | `journal_shortlisted` logged; `updatedAt` bumped; `shortlistedCount` increments |
| WS-INT-03 | Unshortlist | `journal_unshortlisted` logged; count decrements |
| WS-INT-04 | Delete a project that has finder data | Shortlist rows removed |
| WS-INT-05 | Finder holds an `activeProject` that was deleted elsewhere | Frontend handles the `404` (clears it or creates a new project) |
| WS-INT-06 | Project created by the finder has no research field | Shown without error |
| WS-INT-07 | Finder search with and without an active project | Both work |

### 8.17 Frontend component and flow tests (A and B)

Automated if the frontend already has test tooling (adding dev dependencies requires approval); otherwise run as the manual checklist in Section 9.

| ID | Scenario | Expected |
|---|---|---|
| WS-FE-01 | Projects page while loading | Loading state |
| WS-FE-02 | No projects | Empty state with the New Project button |
| WS-FE-03 | Server error on load | Error message with retry; retry works |
| WS-FE-04 | Populated list | Cards show title, field, status, updated time |
| WS-FE-05 | Click New Project | Modal opens; focus is in the title field |
| WS-FE-06 | Submit with blank title | Inline prompt; no request sent |
| WS-FE-07 | Submit valid title | One request; modal closes; success notification; project at the top of the list |
| WS-FE-08 | Double-click submit | Only one project created |
| WS-FE-09 | Esc or Cancel | Modal closes; nothing created |
| WS-FE-10 | Server rejects (`409` cap or `422`) | Message shown inline; modal stays open |
| WS-FE-11 | Search typing | Debounced; one request per pause; page resets to 1 |
| WS-FE-12 | Status filter, sort, pagination controls | Correct requests and results |
| WS-FE-13 | Open a project | Overview page loads by ID |
| WS-FE-14 | Open a nonexistent or foreign ID in the URL | "Project not found" with a link back |
| WS-FE-15 | Refresh on the overview page | Stays on the same project |
| WS-FE-16 | Delete | Confirmation shown; after confirming, removed from the list; cancelling does nothing |
| WS-FE-17 | Delete the active project | `activeProject` cleared |
| WS-FE-18 | Dashboard activity feed | Shows real events; empty state when none; each event is readable text |
| WS-FE-19 | Upload valid file | Progress, then the file card with name, size and expiry time |
| WS-FE-20 | Upload wrong type, too large, empty | The exact messages in Section 7.3 |
| WS-FE-21 | Replace and remove file | Card updates; confirmation for remove |
| WS-FE-22 | File expired | Expired message and upload prompt |
| WS-FE-23 | Set and clear target journal | Overview and list update |
| WS-FE-24 | Logout and log in as another user | No trace of the previous user's projects, ever |
| WS-FE-25 | Token expires mid-session | Redirected to login; no crash |
| WS-FE-26 | Backend stopped | Friendly error, no blank screen |
| WS-FE-27 | Title with XSS text, Unicode, RTL, 300 characters | Displayed as text; layout intact; ellipsis where needed |
| WS-FE-28 | Widths 360, 768, 1280 px | Usable at all sizes |
| WS-FE-29 | Keyboard only | Every action reachable; visible focus; modal traps focus |
| WS-FE-30 | Screen reader labels | Form fields, buttons, status and errors are announced |
| WS-FE-31 | Console | No errors or warnings during the flows |
| WS-FE-32 | `npm run build` | Passes with no TypeScript errors |

### 8.18 Regression

| ID | Scenario | Expected |
|---|---|---|
| WS-REG-01 | Register, log in, session restore, logout | Still work |
| WS-REG-02 | Finder search and shortlist | Still work |
| WS-REG-03 | Compare page and other mock-data pages | Still open without errors |
| WS-REG-04 | Full backend test suite | Green |
| WS-REG-05 | `git diff --stat main -- frontend/` | Only approved files |

---

## 9. End-to-end checklist (run manually before sign-off)

**Part A**
- [ ] Log in as a new user: the Projects page shows the empty state.
- [ ] Click New Project, submit with a blank title: the prompt appears and nothing is created.
- [ ] Create "Test paper" with a research field: success notification; it is first in the list.
- [ ] Open it: the overview shows the details, status `draft`, zero shortlisted journals, and one activity event.
- [ ] Edit the title; the list order and `updatedAt` change; the activity feed shows the edit.
- [ ] Search for part of the title; filter by status; sort by title.
- [ ] Create 21 projects and confirm pagination works.
- [ ] Use the Finder, shortlist a journal with no active project: a project is created and appears in the list with the shortlist count.
- [ ] Delete a project via the confirmation: gone from the list; the activity feed shows the deletion.
- [ ] Refresh on each page: state restores correctly.
- [ ] Log out, log in as a second user: none of the first user's data appears.
- [ ] Try the first user's project URL as the second user: "Project not found".

**Part B**
- [ ] Upload a `.docx`: the file card shows name, size and expiry.
- [ ] Upload a renamed text file as `.docx`: rejected with the right message.
- [ ] Upload a 25 MB file: rejected as too large; nothing left on disk.
- [ ] Replace the file: only one file remains in the project's folder.
- [ ] Remove the file: folder is empty; card returns to the empty state.
- [ ] Set `WORKSPACE_FILE_TTL_MINUTES=1` and `CLEANUP_INTERVAL_MINUTES=1`, upload, wait: file removed, expired message shown, activity shows the purge. Restore the settings afterwards.
- [ ] Stop the server mid-upload, restart: the orphan is removed by the startup sweep.
- [ ] Set a target journal, change it, clear it: always at most one target.
- [ ] Delete a project that has a file: the folder disappears from the storage root.

---

## 10. Definition of done

- [ ] Migration applied; model and schema tests updated; downgrade and upgrade round-trip.
- [ ] All endpoints in Section 5 implemented, owner-scoped, with the error behaviour in Section 5.3.
- [ ] No N+1 queries on list, overview or activity.
- [ ] Files are streamed, validated by content, stored under UUID names, never served statically, and purged automatically.
- [ ] Every test in Section 8 is implemented, or explicitly marked not applicable with a reason in the test file.
- [ ] Frontend shows real data for projects, overview, dashboard activity and the draft file; no other pages changed.
- [ ] Section 9 checklist passed.
- [ ] `backend/README.md` updated (endpoints, settings, storage behaviour, deviations including D8).
- [ ] No secrets committed; `storage/` is git-ignored.
- [ ] `git diff --stat main -- frontend/` lists only approved files.

## 11. Known limitations (say these honestly in the viva)

- One owner per project; no sharing or collaboration.
- One draft file per project; no version history.
- Hard delete only; no archive or undo.
- Time-based deletion is not a secure wipe; "temporary" means up to the configured number of minutes after upload.
- No virus scanning of uploads.
- No rate limiting beyond the project cap (the report mentions rate limits at the gateway; add as hardening later).
- Concurrent edits are last-write-wins.

## 12. Viva talking points

- **What is a workspace?** The container for one manuscript: details, journal shortlist and target, the temporary draft, and an audit log. Later features attach their results to it.
- **Why a `404` for someone else's project?** So users can't discover which project IDs exist.
- **Why is the file not in the database?** Privacy and size: the database holds metadata only; the file is temporary and deleted automatically.
- **How do you guarantee deletion?** Three paths: the user removes it, the project is deleted, or the cleanup job removes it after the time limit; a startup and orphan sweep covers crashes.
- **Why an activity log?** The report promises audit logs in the workspace module; it also feeds the dashboard and will record conversions and compliance runs later.
- **What stops someone uploading a malicious file?** Extension and content checks, size limits, zip-bomb checks, UUID file names, no static serving; the file is never executed or parsed in this feature.

---

## Appendix: Suggested prompts for Antigravity / Claude Code

**W1 (recon)**
> Read `PublishAid_Workspace_Plan.md`. Do Phase W1 only. Do not edit any file. Report the Finder-plan reconciliation table, the frontend findings (project type, status labels, pages, context, helpers) and the list of frontend files you propose to change. Then stop.

**W2 to W6 (backend, Part A)**
> Do Phases W2 to W6. Show me the migration before applying it. Every query must be owner-scoped and return the same 404 for unknown and foreign IDs. Implement the Section 8 tests for Part A, run them, and show me the results and the endpoints in the API docs page. Then stop.

**W7 to W8 (frontend, Part A)**
> Do Phases W7 and W8. Modify only the frontend files I approved. Follow Section 7. Then run the Part A end-to-end checklist and report each item as pass or fail.

**W9 to W12 (backend, Part B)**
> Do Phases W9 to W12. Stream uploads, check content not just extensions, never use client file names on disk, and never return server paths. Inject the clock into the cleanup job so tests do not sleep. Run the Section 8 tests for Part B and report results. Then stop.

**W13 to W14 (frontend and wrap-up, Part B)**
> Do Phases W13 and W14. Use the exact upload messages in Section 7.3. Then run the whole end-to-end checklist and the Definition of Done and report each item as pass or fail. Finish by showing the output of `git diff --stat main -- frontend/`.
