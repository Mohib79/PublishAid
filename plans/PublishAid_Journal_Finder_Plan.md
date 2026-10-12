# PublishAid — Journal Finder Plan (Plan 2 of 2)

**Goal:** make the `/finder` page work for real: a researcher enters a title, abstract and keywords, the backend ranks the catalog journals by semantic similarity, and they can shortlist journals into a project (auto-created if none is active).
**Audience:** Antigravity (implementation) and the team (review and evaluation).
**Requires first:** auth working, and Plan 1 complete (50 journals seeded and embedded).

---

## 0. Hard Rules

1. Work on a new branch `feature/journal-finder`. Commit backend and frontend work as **separate commits**.
2. **Frontend edits are allowed, but only to the files listed in Phase 9.** Do not restyle, reorder or redesign anything. Do not touch any other page (Dashboard, Workspace Manager, Compare, Guidelines, etc.), except where Phase 2 reports that something must keep working.
3. Never fabricate metrics. A missing metric is shown as "N/A", never as `null`, `0` or an invented number.
4. All new endpoints require a valid token (the project's rule: everything except register and login is protected).
5. The embedding model and the text-building function must be **shared** with Plan 1's embedding script. The query side and the journal side must never use different models.
6. Schema changes go through Alembic migrations. Show each migration before applying.
7. Work one phase at a time and stop where the plan says STOP.

---

## 1. Decisions Already Made

| Topic | Decision |
|---|---|
| Input (v1) | Title, abstract and keywords as text. File upload is **not** analysed in v1 (see Phase 9 for what the UI should do) |
| Matching | Embed the query with the same SPECTER model, cosine similarity search in pgvector over `journals.embedding` |
| Result size | With 50 journals, return all ranked results (default limit 20, maximum 50) and filter on the frontend |
| Filters | Real filters on the frontend (publisher, quartile, open access), replacing the hardcoded "Environmental science" demo filter |
| Project rule | **Shortlisting with no active project auto-creates a project** from the current title, abstract and keywords. If a project is already active, the journal is added to it |
| Shortlist vs selected | Separate concepts: `is_shortlisted` (many per project) and `is_selected` (the single target journal, used later by conversion and compliance) |
| Order of work | Matching first (works without projects), then projects, then shortlist, then frontend wiring |

---

## Phase 1 — Prerequisites Check (STOP if any fails)

- [ ] Auth endpoints work and `get_current_user` exists.
- [ ] `SELECT count(*) FROM journals WHERE embedding IS NOT NULL;` returns 50.
- [ ] `pytest -q` is green.
- [ ] The embedding model name constant and `build_journal_text()` exist as a shared module from Plan 1.

If anything is missing, stop and tell the user which earlier plan phase to finish.

---

## Phase 2 — Read-Only Frontend Recon (STOP and report)

Do not edit anything yet. Read and report on:

1. The `Journal` and `Project` types in `frontend/src/types`: exact field names, which are optional, what `quartile` and `openAccessType` values exist.
2. `context/AppContext`: how `journals`, `activeProject`, `toggleShortlistJournal`, `selectedCompareJournalIds` and `toggleCompareJournal` work and where `journals` comes from (mock data).
3. **Every other page that reads `journals`, `activeProject` or the shortlist** (especially the Compare page and the Dashboard). Changing where the data comes from must not break them. List each usage.
4. The API helper created by the auth work (base URL, token handling, error parsing). Reuse it; do not create a second one.
5. Whether a toast/notification component already exists.

Report what you found and propose the exact list of files you intend to change. Wait for approval.

---

## Phase 3 — Embedding Service (Backend)

Create `app/services/embedding.py`:

1. Load the SPECTER model **once at server startup** using FastAPI's lifespan handler, and run one warm-up encode so the first real request is not slow. Keep the model in a module-level singleton; never load it per request.
2. Expose `embed_query(text: str) -> list[float]`. Assert the dimension is 768 at load time.
3. Model name and device come from settings (`EMBEDDING_MODEL`, `EMBEDDING_DEVICE`, default CPU).
4. Log the load time and each encode time.
5. Make the service **replaceable in tests**: the API layer gets it through a dependency, so tests can inject a fake embedder that returns fixed vectors without downloading anything.

Note for the team: the first server start will be slow while the model loads (and downloads the first time). That is expected.

---

## Phase 4 — Matching Service (Backend)

Create `app/services/matching.py`.

### 4.1 Query text
One function `build_query_text(title, abstract, keywords) -> str`, kept in one place so it can be tuned during evaluation. Starting point: title and abstract joined the way SPECTER expects (title, separator, abstract), with keywords appended to the abstract part. Do not hardcode the format anywhere else.

### 4.2 Search
Use pgvector's cosine distance operator through SQLAlchemy:

```python
distance = Journal.embedding.cosine_distance(query_vector)
stmt = (
    select(Journal, (1 - distance).label("similarity"))
    .where(Journal.embedding.is_not(None))
    .order_by(distance)
    .limit(limit)
)
```

### 4.3 Scores and tags
- `rawSimilarity` = cosine similarity (0 to 1), returned for transparency.
- `matchScore` (what the UI shows as a percentage) comes from **one function** `to_match_score(similarity)` so it can be recalibrated in one place. **Default: round(similarity x 100).** After the Phase 6 evaluation, look at the distribution of similarities for correct vs incorrect matches and decide, with the team, whether a rescale is needed. Do not invent a rescale before looking at real numbers. Rank order matters more than the absolute number.
- `matchTag`: rank 1 gets "Best fit"; others none (configurable). The UI already handles a missing tag.

### 4.4 Edge cases
- Empty or whitespace-only input: validation error (see Phase 5).
- Journals with no embedding are skipped (and logged once).
- If fewer than `limit` journals exist, return what exists.

---

## Phase 5 — Endpoints: Catalog and Match

All under an authenticated router. JSON is camelCase to match the frontend (reuse the alias generator from the auth work).

### `POST /journals/match`
Request:
```json
{
  "title": "string (optional)",
  "abstract": "string (optional)",
  "keywords": ["string"],
  "limit": 20,
  "projectId": 12
}
```
Rules:
- At least one of `title` or `abstract` must be non-empty after trimming, else 422 with a clear message.
- `keywords` accepts a list or a comma-separated string (the form field is a single comma-separated input); normalize to a list.
- Size limits: title up to 300 chars, abstract up to 10,000 chars, up to 20 keywords.
- `projectId` is optional. If given and the project belongs to the user, mark results with `isShortlisted`; if it does not belong to the user, return 404 (do not reveal whether it exists).
- Use a plain `def` endpoint (not `async def`) so FastAPI runs the CPU-heavy encode in its threadpool.

Response:
```json
{
  "results": [
    {
      "id": "7",
      "title": "...",
      "publisher": "...",
      "subjectCategory": "...",
      "quartile": "Q1",
      "openAccessType": "...",
      "aimsAndScope": "...",
      "citeScore": null,
      "reviewWeeks": null,
      "acceptanceRate": null,
      "matchScore": 87,
      "rawSimilarity": 0.874,
      "matchTag": "Best fit",
      "isShortlisted": false,
      "homepageUrl": "...",
      "sjr": 2.1,
      "hIndex": 150
    }
  ],
  "meta": { "model": "...", "tookMs": 312, "totalJournals": 50 }
}
```
Adjust the field names and value strings to match exactly what Phase 2 found in the frontend `Journal` type. IDs are returned as strings. Missing metrics are `null`, never invented.

### `GET /journals` and `GET /journals/{id}`
The plain catalog (no ranking), used later by the Compare page and for the shortlist view. Same item shape without the match fields. 404 for an unknown ID.

---

## Phase 6 — Evaluation Harness (do this BEFORE touching the frontend)

The point is to measure how good the matching is, so the team has a real number and can fix problems early.

1. The team prepares `backend/eval/test_cases.csv` with **at least 20 cases**: `abstract,title,true_journal_title`. Each case is a paper that was actually published in one of the 50 journals. Good sources: papers the team knows, or papers retrieved from the journals' own sites or from OpenAlex's records. Stay realistic: include a few easy cases and a few hard, borderline ones. Do not include any case where the abstract text was copied from the journal's own scope page.
2. Write `scripts/eval_matching.py`. For each case, run the same matching function the API uses and compute: **top-1 accuracy, top-3 accuracy, top-5 accuracy, and mean reciprocal rank**. Print per-case results (rank of the true journal and the top 3 predicted) and the overall numbers.
3. Also print the similarity distribution: for each case, the top similarity and the gap between rank 1 and rank 5. This is the data used to decide on score calibration (Phase 4.3).
4. Save the results to `backend/eval/results_<date>.md` so progress can be compared later.

There is no pass/fail threshold set in advance. Report the numbers to the team. If they are poor, investigate in this order: (a) weak or too-short scope texts, (b) the `build_query_text` format, (c) whether keywords help or hurt (run with and without), (d) a different embedding model as a later experiment. Fix the cause, re-run, and keep the saved results.

STOP: show the team the baseline numbers before continuing. Frontend work can proceed in parallel once the endpoint exists, but quality problems should be known first.

---

## Phase 7 — Schema Changes for Projects and Shortlist (one migration)

| Table | Change |
|---|---|
| `projects` | add `keywords` as an array of text (default empty). The UI already treats a project as having keywords |
| `project_journals` | add `is_shortlisted` Boolean NOT NULL default false. Keep `is_selected`. Keep the unique `(project_id, journal_id)` and the "at most one selected per project" partial unique index |

Also decide whether the dashboard's "status pills" need a `status` column on `projects`. **Do not add it in this plan**; note it for the Projects/Dashboard plan.

Show the migration, apply it, verify downgrade/upgrade, update model and schema tests.

---

## Phase 8 — Endpoints: Projects and Shortlist (Backend)

Everything is scoped to the current user. A project that belongs to someone else returns **404**, never 403.

### Projects (minimal CRUD)
- `POST /projects`: `{title, abstract?, keywords?}` returns the project. Title is required (1 to 300 chars); if the user searched with only an abstract, the frontend sends a derived title (see Phase 9).
- `GET /projects`: the current user's projects, newest first.
- `GET /projects/{id}`
- `PUT /projects/{id}`: update title, abstract, keywords.
- `DELETE /projects/{id}`: cascades through shortlist rows (already defined in the schema).

Response fields in camelCase matching the frontend `Project` type from Phase 2.

### Shortlist
- `PUT /projects/{projectId}/shortlist/{journalId}` with optional body `{similarityScore}`: idempotent. Creates the `project_journals` row if needed (or updates it), sets `is_shortlisted = true`, stores `similarity_score`. Returns the updated journal item.
- `DELETE /projects/{projectId}/shortlist/{journalId}`: sets `is_shortlisted = false`. If the row is not `is_selected` either, delete the row.
- `GET /projects/{projectId}/shortlist`: shortlisted journals with full metadata (what the Compare page and shortlist counter will use).
- Unknown journal ID: 404. Journal and project checks happen in one place (a small dependency).

### Backend tests (use the fake embedder)
- match: ranks correctly with controlled fake vectors; empty input returns 422; `projectId` of another user returns 404; null metrics come back as null; requires auth.
- projects: CRUD happy path; user A cannot read, update or delete user B's project (404).
- shortlist: idempotent PUT; DELETE removes; shortlisting a non-existent journal is 404; deleting a project removes its shortlist rows.
- one slower test marked `@pytest.mark.slow` using the **real** model, run manually.

STOP: show the endpoints working in the interactive API docs page, and the test results.

---

## Phase 9 — Frontend Wiring

**Files you may modify** (confirm against the Phase 2 report): `JournalFinderPage`, `context/AppContext`, the `types` file, and the API helper from the auth work. **You may create** one small helper for N/A formatting if none exists. Nothing else.

### 9.1 API layer
Add `matchJournals()`, `createProject()`, `shortlistJournal()`, `unshortlistJournal()`, `getShortlist()` to the existing API helper. Reuse its token handling and error parsing.

### 9.2 Search
- Replace the `setTimeout` mock with a real `matchJournals()` call. Keep the existing loading state.
- **Start with empty fields.** Remove the prefilled demo title, abstract and keywords (the urban-heat text matches nothing in a computer science catalog). Keep prefill from `activeProject` if one exists.
- Put results in page state, and also merge them into the context `journals` list so the Compare page and the shortlist counter keep working (as established in Phase 2). IDs are strings.
- Add the missing **error state**: a clear inline message for a failed request or a timeout, with a retry. The first request after server start can be slow; show the existing loading card text.
- Handle the "file only" case: if the user uploaded a file but entered no title or abstract, do not call the API. Show an inline message that file analysis is coming soon and that they should paste the title and abstract. Do not claim the file was analysed.

### 9.3 Filters
Replace the hardcoded "All / Environmental science / Open access" with filters that make sense for the real catalog: All, publisher chips generated from the results, a quartile filter, and Open access. Client-side filtering only. Keep the existing chip styling.

### 9.4 Cards
- Add an N/A formatting helper. A null `citeScore`, `reviewWeeks` or `acceptanceRate` shows "N/A" and **never** "null weeks" or "null%". Hide the unit when the value is N/A.
- Show `matchScore` as before; show `rawSimilarity` in the button/title tooltip only if there is already a pattern for tooltips.
- Reword text that is no longer true: the loading line that says matching runs "across Scopus and Web of Science" and the footer that says profiles are illustrative demonstration data. New copy should state plainly that results come from a curated set of journals. Keep it short; do not change other copy.

### 9.5 Shortlist and the auto-project rule
- If `activeProject` exists: shortlisting calls `shortlistJournal(activeProject.id, journalId, similarityScore)`.
- If there is **no** active project: first call `createProject({ title, abstract, keywords })` from the current form values, set it as `activeProject`, then shortlist. If the title is empty but the abstract is not, derive a title from the first words of the abstract (document the rule in a comment). If both are empty, block with an inline message.
- Show a small confirmation using the existing notification pattern if there is one, such as "Added to new project: <title>". If there is no notification component, use a short inline text and do not invent a new design.
- **Prevent duplicates:** disable the shortlist button while the request is in flight, and make sure two quick clicks cannot create two projects.
- Optimistic UI is fine, but roll back and show an error if the request fails.
- Unshortlisting calls the DELETE endpoint.
- "My shortlist" count comes from the shortlisted state, as it does now.

### 9.6 Do not
- Do not wire the Dashboard, Workspace Manager (`/projects`) or Compare page to the backend. They still use mock data in this plan; the finder only needs to keep them from crashing. Note any inconsistency you see (for example a project created here not appearing on the Projects page) in your report instead of fixing it.
- Do not implement file text extraction.

### 9.7 Verification
- `npm run build` passes with no TypeScript errors.
- With the backend running and logged in: search returns ranked real journals; filters work; an empty search shows the validation message; stopping the backend shows the error state with retry.
- Shortlisting with no active project creates exactly one project and one shortlist row (check in the database); shortlisting another journal reuses that project; unshortlisting works; a page refresh keeps the shortlist state for the active project if the context restores it (otherwise report this as a known gap).
- Two rapid clicks never create two projects.
- Compare page still opens with the shortlisted journals and does not crash on null metrics.
- `git diff --stat main -- frontend/` lists only the allowed files.

---

## Phase 10 — Documentation and Handoff

Update `backend/README.md` with: the finder endpoints and examples, how the score is computed and why rank matters more than the percentage, how to run the evaluation, known limitations (50 journals, no file analysis, scope text quality drives accuracy, N/A metrics), and a short "Next plans" list: Projects/Dashboard wiring (including project `status` and the activity feed), Compare page wiring, file upload text extraction, then the Guidelines and Compliance features.

---

## Final Acceptance Checklist

- [ ] `POST /journals/match` returns ranked journals for a real abstract in under a few seconds after warm-up.
- [ ] The embedding model loads once at startup, not per request.
- [ ] Evaluation results saved with top-1, top-3, top-5 and MRR on at least 20 cases.
- [ ] Projects and shortlist endpoints work, are owner-scoped, and are tested (including cross-user 404s).
- [ ] `/finder` shows real results with real filters, N/A handling and an error state.
- [ ] Shortlisting with no active project auto-creates exactly one project; with an active project it reuses it.
- [ ] Compare page and shortlist counter still work.
- [ ] No fabricated metrics anywhere.
- [ ] Only the allowed frontend files changed; backend tests green; build passes.

---

## Appendix — Suggested Antigravity prompts

**Phases 1 to 2**
> Read `PublishAid_Journal_Finder_Plan.md`. Do Phases 1 and 2 only. Do not edit any file. Report what you found in the frontend and which files you propose to change, then stop.

**Phases 3 to 5**
> Do Phases 3 to 5. Load the embedding model once at startup. Keep the embedder injectable so tests can fake it. Show the endpoint working in the API docs page, then stop.

**Phase 6**
> Do Phase 6. I will provide `eval/test_cases.csv`. Run the evaluation, save the results file and show me the numbers and the similarity distribution. Do not tune anything until I have seen them.

**Phases 7 to 8**
> Do Phases 7 and 8. Show the migration before applying it. Every project and shortlist query must be scoped to the current user and return 404 for someone else's data.

**Phase 9 to 10**
> Do Phases 9 and 10. Only modify the frontend files approved in Phase 2. After finishing, run the verification list and the Final Acceptance Checklist and report each item as pass or fail.
