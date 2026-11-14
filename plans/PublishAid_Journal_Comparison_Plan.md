# PublishAid — Journal Comparison Plan (Plan 5)

**Feature:** Select two to four journals and see them side by side: publishing model, impact and ranking, charges, review speed, acceptance rate, scope, and (optionally) the submission requirements extracted from their guidelines. Then pick one as the primary target for the project.
**Audience:** Antigravity / Claude Code (implementation) and the team (review, testing, viva).
**Requires first:** Database, Auth, Journal Data, Journal Finder, and Workspace plans. The optional "requirements" comparison also uses the Guideline Extraction plan.
**Report references:** Use Case 4.6 *Side-by-Side Venue Comparison*; Functional Requirement "Journal Selection and Comparison: authors can select candidate journals to review key differences such as review turnaround times, acceptance rates, and publication models"; Section 2.3.1 *Journal Discovery and Comparison*; Table 4.17 *Journal Table*; Table 4.18 *Project Journal Table*; Figure 5.7 *Sequence Diagram for Comparing Journals*.

Order of all plans: Database -> Auth -> Journal Data -> Journal Finder -> Workspace -> Guideline Extraction -> **Journal Comparison (this file)** -> Template Generation -> Conversion and Transformation -> Compliance.

---

## 1. What journal comparison is

The Journal Finder answers "which journals fit my paper?" and returns a ranked list. Ranking is not a decision. A researcher choosing between three plausible journals needs to weigh other things: Is it open access and what does it cost? How prestigious is it? How long does review take? How selective is it? What will the formatting rules demand?

**Journal comparison puts the shortlisted journals in one table, side by side, so the researcher can decide.** Each column is a journal, each row is a metric. The system highlights the best value in each row where "best" is meaningful, shows clearly where data is missing, and lets the researcher set the winner as the project's **primary target**. That choice is what Template Generation, Transformation, and Compliance use later.

### The honest-data principle (the most important design idea)

PublishAid's catalog comes from verified academic publisher listings and curated open metadata. Some metrics, such as proprietary Clarivate Impact Factors, author processing charges (APC), or SCImago journal rank (SJR) metrics, may not be available across every venue in open sources. A comparison feature that hides missing values or invents numbers would be worse than none. The rules are:

1. **A missing value always shows as "N/A".** Never zero, never blank, never an estimate.
2. **Every metric states its source and meaning.** "Quartile" means the SCImago (SJR) quartile or indexed quartile, not Clarivate's proprietary quartile. "2-year mean citedness" comes from OpenAlex and is **not** an Impact Factor, and is never labelled as one.
3. **No overall score and no "winner" badge.** Weighting acceptance rate against cost against prestige is the researcher's judgement. We highlight the best value **per metric** and nothing more.
4. **A completeness indicator per journal** ("9 of 9 core metrics available") so the user knows how much to trust a column.

### Example

| | IEEE TIP | Pattern Recognition | CVIU |
|---|---|---|---|
| Publishing model | Hybrid | Hybrid | Subscription |
| Quartile (SJR) | **Best** Q1 | **Best** Q1 | Q1 |
| CiteScore | 21.7 | 17.3 | 7.2 |
| Impact factor | 15.3 | 9.1 | 3.6 |
| Review turnaround | 12 weeks | 12 weeks | 16 weeks |
| Acceptance rate | 16.0% | 15.0% | 22.0% |
| Publication charge (APC) | N/A | **Best** $0 | $3,500 |

Note the empty cells where data is unavailable: that is the honest picture of what the underlying data provides.

### Mapping to the report's use case (Table 4.6)

| Report step | What the system does |
|---|---|
| Pre-condition: the author has searched and selected at least two journals | The **Compare Selected** button stays disabled until two or more are selected; the Compare page explains what to do when fewer than two are present |
| 1. Author checks candidate journals and clicks **Compare Selected** | Journals are chosen on the finder page (or from browse/shortlist) and the app opens `/compare?ids=…` |
| 1.1 System retrieves metrics and displays them in parallel columns | `GET /journals/compare` returns the table data; the page renders it |
| 2. Author sets one journal as the primary target | **Set as primary target** on a journal column calls the Workspace plan's target-journal endpoint |
| 2.1 System links the chosen journal to the active workspace and confirms the choice | Journal is set as target, success notification is shown, and the column displays a "Primary target" badge |
| Alternative 1-A: more than four journals selected | Message: "At most four journals can be compared at one time." The server also enforces the limit with `422` |

---

## 2. How it fits together

```
React                                   FastAPI                                   PostgreSQL
-----------------                       -------------------------------------     ---------------------
Finder/Browse: Compare toggles          (client state + URL: /compare?ids=7,12)
Compare page             ---GET---->    /journals/compare?ids=&projectId=         journals
  journal picker         ---GET---->    /journals?search=&...                     project_journals
  "Set as primary"       ---PUT---->    /projects/{id}/target-journal/{jid}       guideline_rules (optional)
                                                |
                                                v
                                        Metric registry (one module)
                                        - which rows exist, labels, groups
                                        - type, direction, source notes
                                        - best / differs computation
```

**No new tables and no schema change.** The comparison is computed from data that already exists in PostgreSQL (`journals`, `project_journals`, and `guideline_rules`). Comparisons are not saved: they live in the page URL and client state. The shortlist (saved in the database by the Finder plan) is how a researcher keeps candidates.

Key rules:
1. **One metric registry on the server** defines every row. The frontend renders what it receives and never recomputes "best".
2. **Catalog data is shared; private data is not.** Journals are the same for every user. Similarity scores and requirement rules are private to the requesting user and project.
3. **The URL is the source of truth** on the Compare page, so a refresh or a copied link shows the same comparison.

---

## 3. Decisions

### 3.1 Decisions already made

| Topic | Decision |
|---|---|
| Number of journals | Minimum 2, maximum 4 (report use case 4.6) |
| Presentation | The existing `/compare` page (URL-driven), retaining PublishAid's design kit and components |
| Overall score | **None.** Best value per metric only |
| Missing data | "N/A" everywhere, with a tooltip "Not available from our data sources" |
| "Best" rule | Defined per metric by a `direction` (higher is better, lower is better, or none). Only marked when at least two journals have a value **and** the values are not all equal |
| Metrics without a direction | No highlight. For example acceptance rate ("higher" is not clearly better for selectivity), publisher, ISSN |
| Always-visible rows | The rows the report names stay visible even when empty for every selected journal: publishing model, publication charge (APC), review turnaround, acceptance rate, and quartile. Other metrics hide when no selected journal has a value |
| Impact Factor | Shown if available from catalog data. Never populated from citedness |
| Saved comparisons | Not in this plan. Comparison state lives in the URL and the browser; the shortlist is the saved part |
| Setting the target | Uses the Workspace plan's `PUT /projects/{id}/target-journal/{journalId}`. If no project is active, a chooser lets the user pick an existing project or create one via an inline form |
| Journals visible | Every signed-in user can compare any catalog journal |
| Requirements rows | Optional Part B. They read the requesting user's own active or built-in rule sets only (never another user's) |
| Export | Optional Part B: client-side CSV download of the table as displayed |
| Existing browse & catalog consumers | Must not break. `GET /journals` remains fully compatible with `BrowseJournalsPage.tsx` |

### 3.2 Open decisions with defaults

| Topic | Default |
|---|---|
| Scope excerpt length in the table | 300 characters with "Show more" / "Show less" |
| Number formatting | CiteScore 1 decimal, Impact Factor 1 decimal, SJR 2 decimals, 2-year citedness 2 decimals, h-index integer, APC in USD with thousands separators and no decimals (`$3,500`), acceptance rate as a percentage with 1 decimal (`16.0%`), review turnaround formatted with singular/plural support (`1 week`, `12 weeks`, `5.3 weeks` with trailing `.0` stripped) |
| Zero APC | Shown as "$0" with tooltip "Listed as free to publish" (zero and N/A are distinct facts) |
| Duplicate IDs in the request | Removed (order of first appearance kept), then the 2 to 4 rule is applied |
| Order of columns | The order of `ids` in the request |
| Maximum `ids` accepted before validation | 20 (anything longer is rejected immediately with `422`) |
| Text row equality for `allSame` | Case-insensitive trimmed equality (`val1.strip().lower() == val2.strip().lower()`) |
| Negative or out-of-range values in data | Not marked best; treated as data error / N/A |
| Part B keywords range formatting | Both bounds present and unequal: `"{min} to {max}"`; both present and equal: `"{min}"`; only min: `"At least {min}"`; only max: `"Up to {max}"`; neither present: N/A |
| Part B article types | General rules (`general`, `citation`, `layout`) used by default; note indicating article-type overrides exist |
| Part B CSV export "Best" markers | Omitted from cell text so numeric values remain machine-readable numbers when opened in spreadsheet software |

---

## 4. Metric registry (the heart of the backend)

One module, `app/services/comparison/registry.py`, defines every row. Adding a metric later means adding one entry.

### 4.1 Row definition fields

| Field | Meaning |
|---|---|
| `key` | Stable identifier (camelCase) |
| `label` | Text shown to the user |
| `group` | `overview`, `fit`, `impact`, `cost`, `speed`, `scope`, `requirements` |
| `type` | `text`, `enum`, `number`, `integer`, `percent`, `currency`, `link`, `longtext`, `list` |
| `direction` | `higher`, `lower`, or `none` (what "best" means) |
| `alwaysShow` | Keep the row visible even when every selected journal is N/A |
| `note` | Short source and meaning text shown under the label |
| `completeness` | Whether the row counts towards the per-journal completeness figure |

### 4.2 The rows

| Key | Label | Group | Type | Direction | Always show | Source and note |
|---|---|---|---|---|---|---|
| `publisher` | Publisher | overview | text | none | yes | Journal table |
| `issn` | ISSN | overview | text | none | no | Journal table |
| `subjectCategory` | Subject area | overview | text | none | no | Assigned from controlled list |
| `publishingModel` | Publishing model | overview | enum | none | yes | Journal table `open_access_type` (normalized: `"Open access"`, `"Hybrid"`, `"Subscription"`) |
| `homepage` | Journal website | overview | link | none | no | Journal table `homepage_url` (or N/A if column absent) |
| `matchScore` | Match to your paper | fit | integer 0 to 100 | higher | yes (only when `projectId` provided) | Computed via `to_match_score` from `app.services.matching` |
| `quartile` | Quartile (SJR) | impact | enum Q1 to Q4 | higher is better means Q1 | yes | SCImago journal rank quartile |
| `citeScore` | CiteScore | impact | number | higher | no | Journal table `citescore` |
| `impactFactor` | Impact Factor | impact | number | higher | no | Journal table `impact_factor` |
| `sjr` | SJR score | impact | number | higher | no | SCImago (N/A if column absent) |
| `hIndex` | h-index | impact | integer | higher | no | OpenAlex / SCImago (N/A if column absent) |
| `citedness2yr` | 2-year mean citedness | impact | number | higher | no | OpenAlex citedness (N/A if column absent) |
| `apcUsd` | Publication charge (APC) | cost | currency | lower | yes | OpenAlex APC (N/A if column absent) |
| `reviewWeeks` | Review turnaround | speed | number (weeks) | lower | yes | Journal table `review_weeks` (supports decimal weeks e.g. 5.3) |
| `acceptanceRate` | Acceptance rate | speed | percent | none | yes | Journal table `acceptance_rate` (percentage 0 to 100) |
| `aimsAndScope` | Aims and scope | scope | longtext | none | yes | Official journal page scope text |

Part B adds the **requirements** group (all direction `none`, shown only when `include=requirements` is requested):
- `rulesSource`: "My rules (vN)", "Built-in", or N/A
- `maxWords`: integer word count limit
- `maxAbstractWords`: integer abstract word limit
- `citationStyle`: citation format (e.g. "IEEE", "Vancouver", "APA")
- `columns`: layout column structure ("single", "double", "either")
- `requiredSections`: list of mandatory section headings
- `keywords`: keyword range constraint (e.g. "3 to 6", "At least 3", "Up to 8")

### 4.3 Computed values per row

For each row the server computes, over the journals in the request:
- **`isBest`** per journal, by these rules applied in order:
  1. The row's `direction` is `none` -> nobody is marked.
  2. Fewer than two journals have a value (not N/A) -> nobody is marked.
  3. All non-N/A values are equal -> nobody is marked.
  4. Otherwise mark every journal whose value equals the optimum (the highest value for `higher`, the lowest for `lower`). Ties mark all tied journals.
  Quartile is compared by rank (Q1 is best). Numbers are compared after rounding to 3 decimal places.
- **`allSame`**: true when every journal has the same value, counting N/A as a value (so one N/A and one number is **not** the same). The frontend uses it for "Show only rows that differ".

### 4.4 Per-journal completeness & Safe attribute extraction

Database model attributes are extracted safely using `getattr(journal, col_name, None)` so that fields not present as database columns gracefully resolve to `None` without raising `AttributeError`.

`COMPLETENESS_KEYS` defines the core catalog metrics:
`publisher`, `issn`, `subjectCategory`, `publishingModel`, `quartile`, `citeScore`, `impactFactor`, `reviewWeeks`, `acceptanceRate`. (Total = 9 core metrics; extended metrics like `homepage`, `sjr`, `hIndex`, `citedness2yr`, `apcUsd` are checked safely if columns are later added).
A journal's completeness is `{available, total}` where `available` counts non-null values among them.

---

## 5. API contract

All endpoints require a Bearer token. JSON is camelCase; IDs are strings in JSON and integers in URLs and query strings.

### 5.1 `GET /journals/compare`

> [!IMPORTANT]
> **Routing Precedence:** `@router.get("/compare")` **MUST** be declared **above** `@router.get("/{journal_id}")` in `backend/app/api/journals.py` so FastAPI does not attempt to cast `"compare"` into an integer journal ID.

Query parameters:
- `ids` (required): comma-separated journal IDs, for example `7,12,31`.
- `projectId` (optional): adds private context for that project (the caller must own it).
- `include` (optional): `requirements` adds the requirements rows (Part B).

Validation:
- 2 to 4 unique IDs after removing duplicates (`422` otherwise). At most 20 raw values are accepted.
- Every ID must be a positive integer (`422` otherwise). Whitespace around values is trimmed; empty values (a trailing comma) are ignored.
- Any unknown ID returns `404` via `JSONResponse`:
  ```json
  { "detail": "Journal not found", "missingIds": ["99"] }
  ```
- A `projectId` that is unknown or belongs to someone else returns `404` with `{ "detail": "Project not found" }`.
- Unknown `include` values return `422`.

Response:
```json
{
  "journals": [
    {
      "id": "7",
      "title": "IEEE Transactions on Image Processing",
      "publisher": "IEEE Signal Processing Society",
      "homepageUrl": null,
      "metadataUpdatedAt": "2026-10-11T17:55:23Z",
      "completeness": { "available": 8, "total": 9 },
      "projectContext": {
        "isShortlisted": true,
        "isTarget": false,
        "rawSimilarity": 0.865,
        "matchScore": 63
      }
    }
  ],
  "groups": [
    { "key": "overview", "label": "Overview" },
    { "key": "fit", "label": "Match to your paper" },
    { "key": "impact", "label": "Impact and ranking" },
    { "key": "speed", "label": "Speed and selectivity" },
    { "key": "cost", "label": "Cost" },
    { "key": "scope", "label": "Scope" }
  ],
  "rows": [
    {
      "key": "quartile",
      "label": "Quartile (SJR)",
      "group": "impact",
      "type": "enum",
      "direction": "higher",
      "alwaysShow": true,
      "note": "SCImago journal rank quartile, not Clarivate.",
      "allSame": false,
      "values": [
        { "value": "Q1", "isBest": true },
        { "value": "Q2", "isBest": false }
      ]
    }
  ],
  "notes": [
    "N/A means the value is not available from our data sources.",
    "Quartile is based on SCImago SJR, not Clarivate."
  ],
  "generatedAt": "2026-11-20T10:00:00Z"
}
```

Rules for the response:
- `values` has exactly one entry per journal, in the exact order of `journals`.
- Hidden rows (not `alwaysShow` and N/A for every journal) are **omitted** from `rows`.
- `projectContext` is `null` unless `projectId` was provided. When provided, the `fit` group appears with `matchScore`, computed using `to_match_score` from `app.services.matching`. If a journal has no stored similarity, its `matchScore` is N/A.
- `metadataUpdatedAt` uses the journal's `created_at` timestamp (or `metadata_updated_at` if present).
- No embeddings, no internal fields, no private data from other users.
- Long text is returned in full; the frontend handles excerpting and toggles.

### 5.2 `GET /journals` (Catalog browse & search)

> [!NOTE]
> `GET /journals` and `GET /journals/browse` are already used by `BrowseJournalsPage.tsx`. To preserve complete backwards compatibility, the endpoint continues to return `JournalBrowseResponse`:
> `{ items: JournalItemOut[], total, page, limit, totalPages, categories, publishers }`.

Query parameters accepted:
- `search`: partial case-insensitive match on title, publisher, subject category, ISSN, and aims & scope.
- Filter parameters: `category` (alias `subjectCategory`), `publisher`, `quartile`, `open_access_type` (alias `openAccess`).
- Sorting parameters: `sort_by` (alias `sort`: `title`, `citescore`, `impact_factor`, `review_weeks`, `acceptance_rate`, `quartile`), `sort_order` (alias `order`: `asc`, `desc`).
- Pagination: `page` (default 1), `limit` (alias `pageSize`: default 10 or 20, max 100).

### 5.3 Endpoints reused from earlier plans

| Endpoint | Plan | Use here |
|---|---|---|
| `GET /projects/{id}/shortlist` | Finder / Workspace | "Add from shortlist" in the journal picker |
| `PUT /projects/{id}/target-journal/{journalId}` | Workspace | Set as primary target |
| `DELETE /projects/{id}/target-journal` | Workspace | Clear primary target |
| `GET /projects` | Workspace | Project chooser when setting a target without an active project |
| Batch ruleset resolver | Guideline Extraction | Requirements rows (Part B) |

### 5.4 Error Handling & Status Codes

| Status | When | Response body |
|---|---|---|
| 401 | Missing, invalid, or expired token | `{ "detail": "Not authenticated" }` |
| 404 | Unknown journal ID in compare | `{ "detail": "Journal not found", "missingIds": ["99"] }` |
| 404 | Unknown or foreign `projectId` | `{ "detail": "Project not found" }` |
| 422 | Fewer than 2 or more than 4 IDs, malformed IDs, bad `include`, bad sort/paging | `{ "detail": "..." }` |
| 500 | Unexpected error | Generic message; never a stack trace |

---

## 6. Implementation plan

Two parts. **Part A** is the full comparison of catalog metrics with target setting. **Part B** adds the requirements rows and the CSV export. Complete and verify Part A before Part B.

### Hard rules for the agent (paste at the top of every session)

1. Work on a new branch `feature/comparison`. Commit backend and frontend separately.
2. Frontend edits only to the approved files:
   - `frontend/src/pages/JournalComparisonPage.tsx`
   - `frontend/src/context/AppContext.tsx`
   - `frontend/src/lib/api.ts`
   - `frontend/src/types/index.ts`
   - `frontend/src/pages/JournalFinderPage.tsx`
   - `frontend/src/pages/BrowseJournalsPage.tsx`
   - `frontend/src/pages/GuidelinesTemplatesPage.tsx` (Part B only)
3. **No database schema changes.** Extract all fields safely using `getattr`.
4. Never show, store, or return a made-up value. Missing is N/A.
5. Never compute "best" in the frontend. The server decides.
6. Never include another user's private data in a response.
7. Work one phase at a time and stop where the plan says STOP.

---

### PART A: Comparison of catalog metrics

#### Phase C1: Pre-flight, reconciliation, and frontend recon (STOP and report)

1. Confirm auth, journals data, finder, workspace, and `pytest -q` are healthy.
2. **Data coverage report.** Run a query on the `journals` table and report, for each metric in Section 4.2, how many of the 50 journals have a value.
3. **Reconcile with earlier plans:**
   - Confirm `GET /journals` and `GET /journals/{id}` exist.
   - Confirm `GET /projects/{id}/shortlist` exists.
   - Confirm `PUT /projects/{id}/target-journal/{journalId}` and `DELETE /projects/{id}/target-journal` exist.
   - Confirm `to_match_score` in `app/services/matching.py` is ready for reuse.
4. **Read-only frontend recon:**
   - Review `JournalComparisonPage.tsx` and identify components to upgrade (table, chips, picker, badges).
   - Review `AppContext.tsx`: verify `selectedCompareJournalIds` initialization and `activeProject` fallback.
   - Verify `BrowseJournalsPage.tsx` and `JournalFinderPage.tsx` compare buttons.
5. Propose the exact list of frontend files to change and **wait for approval**.

#### Phase C2: Metric registry (pure code, tested first)

Build `app/services/comparison/registry.py`:
- Registry row definitions with groups, labels, directions, notes, and completeness flags.
- Safe metric extraction from journal records with casing normalization (`"Open access"`).
- Best value calculation honoring directions, ties, and N/A values.
- `allSame` computation.
- Pure functions tested with unit tests **JC-REG, JC-BST, JC-FMT-API**.

#### Phase C3: Compare endpoint

Build `GET /journals/compare` in `app/api/journals.py`:
- Registered **above** `GET /journals/{journal_id}`.
- Single database query for journals preserving request order.
- Single query for `project_journals` if `projectId` is provided.
- Returns `missingIds` on 404 via `JSONResponse`.
- Write **JC-CMP, JC-PRJ, JC-SEC, JC-PERF** tests.

#### Phase C4: Catalog list upgrade

Upgrade `GET /journals` in `app/api/journals.py` to support aliases (`pageSize`, `sort`, `order`, `subjectCategory`, `openAccess`) while preserving `JournalBrowseResponse` and existing parameter names. Write **JC-CAT** tests.

#### Phase C5: Backend checkpoint (STOP)

Run the full test suite (`pytest -q`). Test the compare endpoint via Swagger docs with 2, 3, and 4 journals. Report test results and wait for approval.

#### Phase C6: Frontend wiring (approved files only)

1. **`lib/api.ts`:**
   - Add `compareJournals(ids: string[], projectId?: string, includeRequirements?: boolean)`.
   - Update `apiRequest` / error parsing to preserve HTTP status and `missingIds`.
2. **`context/AppContext.tsx`:**
   - Initialize `selectedCompareJournalIds` to `[]` (clear mock IDs).
   - Reset `selectedCompareJournalIds` to `[]` on `logout()`.
   - Add `setSelectedCompareJournalIds(ids: string[])`.
   - Replace `window.alert` with inline/toast notification: `"At most four journals can be compared at one time."`
   - Adjust `activeProject` fallback so unassigned project states can be handled by the project chooser.
3. **`JournalFinderPage.tsx` & `BrowseJournalsPage.tsx`:**
   - Update Compare Selected button to navigate to `/compare?ids=...`.
4. **`JournalComparisonPage.tsx`:**
   - Read `ids` from URL search params.
   - Render table with grouped rows, sticky label column, and horizontal scroll.
   - Journal chips with remove action; Add journal picker with Shortlist and Catalog Search tabs.
   - Differences toggle ("Show only rows that differ").
   - "Set as primary target" with inline project chooser if no active project.
   - Completeness footer and expandable data notes.

#### Phase C7: Part A verification (STOP)

Run manual checklist (Section 9 Part A), frontend build (`npm run build`), and verify `git diff --stat main -- frontend/`.

---

### PART B: Requirements rows and export

#### Phase C8: Requirements rows

Implement `include=requirements`:
- Add `resolve_effective_rules_for_journals(db, user_id, journal_ids)` in `app/services/guidelines/ruleset_service.py` to batch-resolve rules in one SQL query.
- Populate `rulesSource`, `maxWords`, `maxAbstractWords`, `citationStyle`, `columns`, `requiredSections`, and `keywords`.
- Update `JournalComparisonPage.tsx` to display requirements rows with "Not extracted yet" linking to `/guidelines?journalId={id}`.
- Update `GuidelinesTemplatesPage.tsx` to read `journalId` from query params on mount.
- Write **JC-REQ** tests.

#### Phase C9: CSV export (client-side)

Implement **Download CSV** in `JournalComparisonPage.tsx`:
- Exports visible rows only.
- Encodes as UTF-8 with BOM (`\uFEFF`).
- Escapes formula injection triggers (`=`, `+`, `-`, `@`) with a leading `'`.
- Write **JC-EXP** tests.

#### Phase C10: Final verification and documentation

Run full Section 9 checklist. Update `backend/README.md` and verify `git diff --stat main -- frontend/`.

---

## 7. Frontend details

### 7.1 Selecting journals
- Toggle Compare adds/removes journals from comparison set (max 4). Selecting a 5th displays: *"At most four journals can be compared at one time."*
- **Compare selected (N)** button enables at N >= 2 and navigates to `/compare?ids=1,2,3`.
- Opening `/compare` with no `ids`: uses context selection if >= 2, otherwise renders the fewer-than-two placeholder.

### 7.2 The Compare page
1. **Header:** Title, count, removable chips, and **Add journal** button.
2. **Picker Modal:** Tabs for "From my shortlist" (active project required) and "Search catalog" (debounced query). Already-selected journals are disabled.
3. **Fewer than two journals:** Explanatory banner with chips, picker, and link to Journal Finder.
4. **Table:** Semantic markup (`<table className="min-w-full">`, `<th>` with scope), sticky first column for metric labels, collapsible group headers (`Overview`, `Fit`, `Impact`, `Cost`, `Speed`, `Scope`, `Requirements`).
5. **Cells:** Formatted per Section 3.2. Best values marked with a "Best" pill badge. N/A values styled with muted text and accessible tooltip. Long scope text clamped with "Show more".
6. **Differences toggle:** Uses `allSame` flag from server response.
7. **Column footer:** Completeness indicator ("8 of 9 metrics available"), updated date, and target status.
8. **Primary target:** "Set as primary target" button. If no active project, opens a modal listing existing projects with an inline "Create new project" option.
9. **Error recovery:** If an unknown ID returns 404 with `missingIds`, the app removes those IDs, displays an alert, and refreshes the remaining set.

---

## 8. Test catalog

### 8.1 Metric registry (unit tests, no database)

| ID | Scenario | Expected |
|---|---|---|
| JC-REG-01 | Registry contains Section 4.2 rows with valid groups and types | Matches specification |
| JC-REG-02 | Every row has a label and unique key | Verified |
| JC-REG-03 | Value extraction with all fields populated | Exact mapping |
| JC-REG-04 | Value extraction with null/missing optional attributes | Returns `None`, no `AttributeError` |
| JC-REG-05 | `publishingModel` normalizes `"Open Access"` to `"Open access"` | Correct string |
| JC-REG-06 | `impactFactor` reads only `impact_factor` column | Independent of citedness |
| JC-REG-07 | `citedness2yr` label does not mention "Impact Factor" | Verified |
| JC-REG-08 | Quartile values Q1..Q4 map to ranks 1..4 | Q1 = best rank |
| JC-REG-09 | Unexpected quartile values (`Q5`, empty) | Evaluates as N/A |
| JC-REG-10 | Hidden-row logic: not `alwaysShow` and all N/A | Row omitted |
| JC-REG-11 | Hidden-row logic: `alwaysShow` and all N/A | Row kept |
| JC-REG-12 | Hidden-row logic: not `alwaysShow` and at least one value present | Row kept |
| JC-REG-13 | Completeness counting excludes `matchScore` and `aimsAndScope` | Verified |
| JC-REG-14 | Completeness for journal with all optional fields null | `{available: 0, total: 9}` |
| JC-REG-15 | Empty or whitespace text columns | Treated as N/A |

### 8.2 Best value and differences logic

| ID | Scenario | Expected |
|---|---|---|
| JC-BST-01 | `higher` direction: 1.2, 2.1, 1.9 | Only 2.1 marked best |
| JC-BST-02 | `lower` direction (APC): 3500, 0, 2000 | Only 0 marked best |
| JC-BST-03 | Tie at optimum (2.1, 2.1, 1.0) | Both 2.1 marked best |
| JC-BST-04 | All values equal | Nobody marked best; `allSame` = true |
| JC-BST-05 | Only one journal has a value | Nobody marked best |
| JC-BST-06 | Two journals have values, one is N/A | Better of two marked best; N/A never marked |
| JC-BST-07 | All N/A | Nobody marked best; `allSame` = true |
| JC-BST-08 | `direction: none` (acceptance rate, publisher) | Nobody marked best |
| JC-BST-09 | Quartile Q1, Q2, Q3 | Q1 marked best |
| JC-BST-10 | Numbers differing at 4th decimal (1.2341 vs 1.2342) | Equal after rounding to 3 decimals |
| JC-BST-11 | `allSame` with one N/A and one number | `false` |
| JC-BST-12 | `allSame` with N/A, N/A | `true` |
| JC-BST-13 | `allSame` for text rows differing in case (`IEEE` vs `ieee`) | Equal after case-insensitive trimming |
| JC-BST-14 | APC zero vs null | 0 is a valid value; null is N/A |
| JC-BST-15 | Decimal review weeks (5.3 vs 12.0) | 5.3 marked best for `lower` |
| JC-BST-16 | Negative or out-of-range values in data | Not marked best |
| JC-BST-17 | List rows (required sections) | No best; `allSame` computed by set equality |

### 8.3 Compare endpoint: validation

| ID | Scenario | Expected |
|---|---|---|
| JC-CMP-01 | Two valid IDs | 200 OK with 2 columns |
| JC-CMP-02 | Three valid IDs | 200 OK with 3 columns |
| JC-CMP-03 | Four valid IDs | 200 OK with 4 columns |
| JC-CMP-04 | Five IDs | 422 with message stating max 4 |
| JC-CMP-05 | One ID | 422 with message stating min 2 |
| JC-CMP-06 | Empty or omitted `ids` parameter | 422 |
| JC-CMP-07 | Duplicate IDs `7,7,12` | Deduplicated to 2 journals; 200 OK |
| JC-CMP-08 | Duplicates reducing to one ID `7,7` | 422 |
| JC-CMP-09 | Non-numeric IDs `7,abc` | 422 |
| JC-CMP-10 | Negative, zero, or overflow IDs | 422 |
| JC-CMP-11 | Whitespace around IDs `7, 12` | Trimmed and accepted |
| JC-CMP-12 | More than 20 raw IDs | 422 rejected prior to DB call |
| JC-CMP-13 | Unknown ID among valid IDs | 404 with `missingIds` list in JSONResponse |
| JC-CMP-14 | No token / invalid token | 401 Unauthorized |
| JC-CMP-15 | Column order in response | Matches request `ids` order |
| JC-CMP-16 | Response keys | camelCase only; IDs are strings |
| JC-CMP-17 | URL route precedence | `/journals/compare` does not match `/{journal_id}` |

### 8.4 Project context (private data)

| ID | Scenario | Expected |
|---|---|---|
| JC-PRJ-01 | No `projectId` provided | `projectContext` is null; `fit` group omitted |
| JC-PRJ-02 | Own `projectId` with shortlisted journals | `projectContext` populated; `matchScore` present |
| JC-PRJ-03 | `matchScore` computation | Matches `to_match_score` from `matching.py` |
| JC-PRJ-04 | Journal in request but not in project | `isShortlisted: false`, `matchScore: null` |
| JC-PRJ-05 | Target journal | `isTarget: true` on corresponding column |
| JC-PRJ-06 | Foreign or nonexistent `projectId` | 404 Project not found |
| JC-PRJ-07 | Cross-user isolation | User B cannot view User A's project scores |

### 8.5 Requirements rows (Part B)

| ID | Scenario | Expected |
|---|---|---|
| JC-REQ-01 | `include=requirements` with active user rule set | User rules populated |
| JC-REQ-02 | Journal with only built-in rule set | `rulesSource: "Built-in"` |
| JC-REQ-03 | Journal with both user and built-in rules | User rule takes precedence |
| JC-REQ-04 | Journal with no rule set | Requirements cells return N/A |
| JC-REQ-05 | Another user's rule set for same journal | Never included in response |
| JC-REQ-06 | Batch resolution performance | Executed in a single SQL query |
| JC-REQ-07 | Keywords range format | Formatted per Section 3.2 rules |

### 8.6 Catalog list & search (Backwards compatibility)

| ID | Scenario | Expected |
|---|---|---|
| JC-CAT-01 | Default request | Returns 200 OK with `JournalBrowseResponse` shape |
| JC-CAT-02 | Search across title, publisher, subject | Matches case-insensitively |
| JC-CAT-03 | Category / subjectCategory alias | Filter applied correctly |
| JC-CAT-04 | OpenAccess filter alias | Filter applied correctly |
| JC-CAT-05 | Pagination with `pageSize` alias | Slices correctly, total preserved |
| JC-CAT-06 | Existing `BrowseJournalsPage` tests | Pass without regression |

### 8.7 Frontend tests

| ID | Scenario | Expected |
|---|---|---|
| JC-FE-SEL-01 | Compare toggle on result card | Toggles selection; updates badge |
| JC-FE-SEL-02 | 5th journal selected | Displays "At most four journals can be compared at one time." |
| JC-FE-SEL-03 | Logout | Resets comparison selection to empty |
| JC-FE-TBL-01 | Open `/compare?ids=7,12` | Fetches and renders 2 columns |
| JC-FE-TBL-02 | Refresh page | Restores comparison from URL query |
| JC-FE-TBL-03 | Unknown ID 404 | Removes missing ID and displays notification |
| JC-FE-TBL-04 | Differences toggle | Hides rows where `allSame` is true |
| JC-FE-TBL-05 | Set as primary target | Updates target badge; calls API |
| JC-FE-TBL-06 | Set target without active project | Opens project chooser modal |

---

## 9. End-to-end checklist (manual, before sign-off)

**Part A**
- [ ] On Journal Finder, search with an abstract: selecting 1 journal keeps Compare Selected disabled; selecting a 2nd enables it.
- [ ] Select a 5th journal: notification shows "At most four journals can be compared at one time."
- [ ] Open `/compare?ids=...`: displays columns, grouped metrics, best badges, and N/A for missing values.
- [ ] Toggle "Show only rows that differ": identical rows hide smoothly.
- [ ] Refresh the page: URL maintains the comparison state.
- [ ] Remove a journal chip down to 1 journal: displays fewer-than-two placeholder and picker.
- [ ] Add a journal via the picker (Shortlist and Catalog tabs).
- [ ] Click "Set as primary target" with an active project: badge updates, workspace reflects choice.
- [ ] Click "Set as primary target" without an active project: project chooser modal opens and allows project selection or creation.
- [ ] Log out and log in as another user: comparison selection is cleared; private project data is isolated.

**Part B**
- [ ] Enable requirements comparison: displays rule sources and extracted constraints.
- [ ] Unextracted journals display "Not extracted yet" with a link opening `/guidelines?journalId={id}`.
- [ ] Click "Download CSV": downloads UTF-8 BOM CSV with formula injection escaped.

---

## 10. Definition of done

- [ ] `GET /journals/compare` implemented with constant query count, route precedence above `/{journal_id}`, and zero DB migrations.
- [ ] Metric registry defines rows with safe attribute extraction (`getattr`) and casing normalization.
- [ ] `GET /journals` supports search, filters, and aliases without breaking `BrowseJournalsPage.tsx`.
- [ ] Missing data displays as N/A; no fabricated numbers; no composite scores.
- [ ] 2-to-4 limit enforced on client and server.
- [ ] Compare page is URL-driven, refresh-safe, and accessible.
- [ ] Part B batch rule resolver and safe CSV download implemented.
- [ ] Automated tests pass (`pytest -q`, `npm run build`).

---

## 11. Known limitations (for viva and report)

- Missing metrics in public databases are honestly shown as N/A rather than estimated.
- The quartile represents indexed SCImago (SJR) rankings, which may differ from Clarivate.
- Comparison tables are view-level states reflected in URLs rather than separate database entities; shortlists serve as the persistent candidate store.
- Coverage is scoped to the catalog's verified venues.
- Submission requirements rows are available only for venues with extracted guideline rulesets.

---

## Appendix: Suggested prompts for Antigravity / Claude Code

**C1 (Recon & Pre-flight)**
> Read `PublishAid_Journal_Comparison_Plan.md`. Perform Phase C1 only. Inspect current database rows, route handlers, and frontend components. Report metric coverage and confirmed file lists, then stop.

**C2 to C5 (Backend Part A)**
> Execute Phases C2 through C5. Implement `app/services/comparison/registry.py` with safe attribute extraction, `GET /journals/compare` placed above `/{journal_id}`, and catalog aliases. Run `pytest -q` and report test results.

**C6 to C7 (Frontend Part A)**
> Execute Phases C6 and C7. Wire `JournalComparisonPage.tsx`, update `AppContext.tsx` (reset mock IDs), and connect `JournalFinderPage.tsx` and `BrowseJournalsPage.tsx`. Verify with `npm run build`.

**C8 to C10 (Part B & Handoff)**
> Execute Phases C8 through C10. Add batch rule resolver in `ruleset_service.py`, connect requirements rows and guidelines deep-linking, and add safe CSV export. Run tests and verify `git diff --stat main -- frontend/`.
