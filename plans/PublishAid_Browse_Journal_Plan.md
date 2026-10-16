# PublishAid — Browse Journal Catalog Plan

**Goal:** create a dedicated `/browse` catalog discovery interface and backend filtering service: researchers can explore all peer-reviewed journals in the database, search across titles and scopes, filter across subject areas, publishers, quartiles, and open access types, sort by metrics (CiteScore, Impact Factor, review speed, acceptance rate), switch between Grid and Table views, inspect detailed journal profile modals, and shortlist or select venues for side-by-side comparison.
**Audience:** Antigravity (implementation) and the team (review and evaluation).
**Requires first:** database setup (`PublishAid_Database_Plan.md`), auth working (`PublishAid_Auth_Plan.md`), and journal catalog seeded (`PublishAid_Journal_Data_Plan.md`).
**Comes after:** Journal Data (`PublishAid_Journal_Data_Plan.md`). **Comes before / companion to:** `PublishAid_Journal_Finder_Plan.md`.

Order of core journal plans: Database -> Auth -> Journal Data -> **Browse Journal (this file)** -> Journal Finder.

---

## 0. Hard Rules

1. Work on a new branch `feature/browse` (or `feature/browse-journal`). Commit backend and frontend work as **separate commits**.
2. **Backend edits are strictly scoped** to `backend/app/api/journals.py`, `backend/app/schemas/journal.py`, `backend/app/main.py`, and `backend/tests/test_journals.py`. Do not alter database models or Alembic migrations unless an explicit schema deficit is identified and approved.
3. **Frontend edits are strictly scoped** to `frontend/src/pages/BrowseJournalsPage.tsx`, `frontend/src/lib/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/components/layout/TopBar.tsx`, and `frontend/src/components/common/Button.tsx`. Do not restyle or refactor other pages (Dashboard, Projects, Finder, Compare, Guidelines).
4. **Never fabricate metrics.** If a metric (`citescore`, `impact_factor`, `review_weeks`, `acceptance_rate`) is missing or NULL in the database, return it as `null` in the API and display `"N/A"` in the frontend. Never display `0`, `"null weeks"`, or an invented number.
5. **All catalog browse endpoints require authentication.** Include the `get_current_user` dependency on all router endpoints (PublishAid's security rule: everything except register, login, and health is protected).
6. **API serialization must use camelCase.** Pydantic response schemas must configure `alias_generator=to_camel` and `populate_by_name=True` so frontend TypeScript models receive `subjectCategory`, `citeScore`, `openAccessType`, `totalPages`, etc., seamlessly.
7. **Database querying must be efficient.** Search, filtering, sorting, and pagination (`LIMIT`, `OFFSET`) must execute at the SQL database layer, not in Python memory.
8. Work one phase at a time and stop where the plan says STOP.

---

## 1. Decisions Already Made

| Topic | Decision | Source / Rationale |
|---|---|---|
| Dedicated Route | `/browse` accessible from the primary sidebar and top navigation | Allows direct catalog discovery without requiring paper upload or semantic input |
| Endpoints | `GET /journals` and alias `GET /journals/browse` for paginated browsing; `GET /journals/{id}` for single journal details. Mounted at `/journals` and `/api/journals` | SRS / API architecture compatibility across clients and test suites |
| Keyword Search | Substring match (`ILIKE`) across `journal_title`, `publisher`, `subject_category`, `issn`, and `aims_and_scope` | Researchers can search by title, venue abbreviation, topic, or ISSN in a single input |
| Categorical Filters | Subject Area (`subject_category`), Publisher (`publisher`), Quartile (`quartile`), and Open Access Type (`open_access_type`) | Real faceted filtering matching academic discovery workflows; `"all"` value bypasses the filter |
| Dynamic Facets | API returns distinct lists of `categories` and `publishers` present in the database | Filter dropdowns stay automatically synchronised with catalog contents without hardcoding |
| Sorting | Flexible sorting on `title`, `citescore`, `impact_factor`, `review_weeks`, `acceptance_rate`, `quartile` with `sort_order` (`asc` / `desc`) | Researchers can prioritise high-impact venues or fast turnaround; SQL uses `.nulls_last()` |
| Pagination | 1-indexed `page` and configurable `limit` (default 10, max 100), returning `total`, `totalPages`, `page`, and `limit` | Prevents over-fetching and supports clean UI pagination controls |
| View Modes | Dual toggle: **Grid View** (rich cards with badges & metric grids) and **Table View** (dense tabular layout for rapid scanning) | Accommodates both detailed exploration and rapid side-by-side scanning |
| Journal Profile Modal | In-page dialog displaying complete metadata, full aims & scope, one-click copy button, and link to official homepage | Avoids disruptive page reloads while providing complete venue intelligence |
| AppContext Integration | Reads and toggles `isShortlisted` via `toggleShortlistJournal` and compare selection via `toggleCompareJournal` (max 4) | Seamlessly interoperates with the Compare page (`/compare`) and user shortlist workflows |
| UI Responsiveness & UX | 300ms debounced search, clear input button, loading skeletons/spinner, inline error recovery, and empty state with reset filter CTA | Professional, polished researcher experience matching PublishAid's design standards |

---

## Phase 1 — Prerequisites Check (STOP if any fails)

Before writing any new browse code, verify:

- [ ] PostgreSQL container is healthy and Alembic migrations are at `head`.
- [ ] Database contains the seeded journal catalog:
  ```sql
  SELECT count(*) FROM journals;
  ```
  Returns at least 50.
- [ ] Authentication system works and `get_current_user` dependency exists in `app/api/deps.py`.
- [ ] `pytest -q` is green.
- [ ] Frontend development server runs cleanly (`npm run dev`).

If any prerequisite is missing, stop and notify the team before proceeding.

---

## Phase 2 — Architecture & API Contract Recon (STOP and report)

Inspect and document the existing contracts:

1. **Frontend Types (`frontend/src/types/index.ts`)**:
   Verify the `Journal` interface structure:
   - `id: string`
   - `title: string`
   - `publisher: string`
   - `issn: string`
   - `subjectCategory: string`
   - `citeScore: number` (nullable / optional in live data)
   - `impactFactor: number` (nullable / optional in live data)
   - `quartile: 'Q1' | 'Q2' | 'Q3' | 'Q4'`
   - `aimsAndScope: string`
   - `openAccessType: 'Open access' | 'Hybrid' | 'Subscription'`
   - `reviewWeeks: number` (nullable / optional in live data)
   - `acceptanceRate: number` (nullable / optional in live data)
   - `isShortlisted?: boolean`
   - `matchScore?: number`
   - `matchTag?: string`
2. **Context Integration (`frontend/src/context/AppContext.tsx`)**:
   Verify how `journals`, `toggleShortlistJournal`, `selectedCompareJournalIds`, and `toggleCompareJournal` are exposed.
3. **Navigation Components**:
   Inspect `Sidebar.tsx` and `TopBar.tsx` for route link patterns, icons (`Library`), and active state highlighting.
4. **API Client (`frontend/src/lib/api.ts`)**:
   Confirm helper methods `apiRequest` and `getStoredToken` handles `Authorization: Bearer <token>` automatically.

Report findings and file modification scope before creating endpoints.

---

## Phase 3 — Pydantic Schemas (Backend)

Create `backend/app/schemas/journal.py`:

### 3.1 `JournalItemOut` Schema
Serialises journal rows into camelCase JSON for the frontend:
- `id`: string representation of `journal_id`.
- `title`: `journal_title`.
- `publisher`: `publisher`.
- `issn`: optional string.
- `subject_category`: optional string (`subjectCategory`).
- `cite_score`: optional float (`citeScore`).
- `impact_factor`: optional float (`impactFactor`).
- `quartile`: optional string (`Q1`, `Q2`, `Q3`, `Q4`).
- `aims_and_scope`: string (`aimsAndScope`).
- `open_access_type`: optional string (`openAccessType`).
- `review_weeks`: optional integer (`reviewWeeks`).
- `acceptance_rate`: optional float (`acceptanceRate`).

Include a `@model_validator(mode="before")` to cleanly extract attributes from both SQLAlchemy ORM `Journal` instances and raw dictionaries:
```python
@model_validator(mode="before")
@classmethod
def map_journal_attributes(cls, data: Any) -> Any:
    if hasattr(data, "journal_id"):
        return {
            "id": str(data.journal_id),
            "title": data.journal_title,
            "publisher": data.publisher,
            "issn": data.issn,
            "subjectCategory": data.subject_category,
            "citeScore": data.citescore,
            "impactFactor": data.impact_factor,
            "quartile": data.quartile,
            "aimsAndScope": data.aims_and_scope,
            "openAccessType": data.open_access_type,
            "reviewWeeks": data.review_weeks,
            "acceptanceRate": data.acceptance_rate,
        }
    ...
```

### 3.2 `JournalBrowseResponse` Schema
Envelope schema for paginated responses:
- `items`: `list[JournalItemOut]`
- `total`: integer total matching records
- `page`: current page (1-indexed)
- `limit`: items per page
- `total_pages`: computed total pages (`totalPages`)
- `categories`: list of distinct subject categories available in DB
- `publishers`: list of distinct publishers available in DB

---

## Phase 4 — API Router & Query Engine (Backend)

Create `backend/app/api/journals.py`:

### 4.1 Route Endpoints
Mount an `APIRouter(prefix="/journals", tags=["journals"])`.

#### `GET /journals` and `GET /journals/browse`
Accepts query parameters:
- `search: Optional[str] = Query(None)`
- `category: Optional[str] = Query(None)`
- `quartile: Optional[str] = Query(None)`
- `publisher: Optional[str] = Query(None)`
- `open_access_type: Optional[str] = Query(None)`
- `sort_by: str = Query("title")` (options: `title`, `citescore`, `impact_factor`, `review_weeks`, `acceptance_rate`, `quartile`)
- `sort_order: str = Query("asc")` (`asc` or `desc`)
- `page: int = Query(1, ge=1)`
- `limit: int = Query(10, ge=1, le=100)`
- `db: Session = Depends(get_db)`
- `current_user: User = Depends(get_current_user)`

Query Building Rules:
1. **Search**: if present, apply `or_` with `ilike` across `journal_title`, `publisher`, `subject_category`, `issn`, and `aims_and_scope`.
2. **Filters**: for each filter, if specified and not `"all"`, add `.where(...)` filter.
3. **Count**: execute `select(func.count()).select_from(query.subquery())` to get exact total matching records before pagination.
4. **Sorting**: map `sort_by` to the model column. If `sort_order == "desc"`, apply `.desc().nulls_last()`, else `.asc().nulls_last()`.
5. **Pagination**: compute `offset_val = (page - 1) * limit`, apply `.offset(offset_val).limit(limit)`.
6. **Facets**: query distinct non-null `Journal.subject_category` and `Journal.publisher` ordered alphabetically.
7. Return `JournalBrowseResponse`.

#### `GET /journals/{journal_id}`
- Retrieves a single journal by integer primary key.
- If not found, raises `HTTPException(status_code=404, detail="Journal with ID {journal_id} not found")`.
- Returns validated `JournalItemOut`.

### 4.2 Router Mounting
In `backend/app/main.py`:
- Import `journals_router` from `app.api.journals`.
- Mount `app.include_router(journals_router)`.
- Mount `app.include_router(journals_router, prefix="/api")` to satisfy API prefix routing.

---

## Phase 5 — Backend Test Suite (Pytest)

Create `backend/tests/test_journals.py`:

Write automated tests using FastAPI's `TestClient` with authenticated test fixtures:

1. `test_browse_journals_requires_auth`: unauthenticated request to `/journals/browse` returns `401 Unauthorized`.
2. `test_browse_journals_authenticated_returns_paginated_list`: request with valid `Bearer` token returns `200 OK`, valid pagination envelope (`total`, `page`, `limit`, `totalPages`, `categories`, `publishers`), and list of journal objects.
3. `test_browse_journals_filter_by_publisher`: querying `?publisher=ACM` returns only ACM journals.
4. `test_browse_journals_filter_by_quartile`: querying `?quartile=Q1` returns only Q1 journals.
5. `test_browse_journals_search_keyword`: searching for a known keyword returns matching journals across title or aims & scope.
6. `test_get_single_journal`: fetching a valid ID returns `200` with the matching journal; non-existent ID returns `404 Not Found`.

Verification:
```powershell
pytest -v backend/tests/test_journals.py
```
All tests must pass cleanly.

---

## Phase 6 — Frontend API Client Layer

Update `frontend/src/lib/api.ts`:

### 6.1 Parameter & Response Types
```typescript
export interface BrowseJournalsParams {
  search?: string;
  category?: string;
  quartile?: string;
  publisher?: string;
  openAccessType?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  page?: number;
  limit?: number;
}

export interface BrowseJournalsResponse {
  items: Journal[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
  categories: string[];
  publishers: string[];
}
```

### 6.2 Client Functions
Implement:
1. `browseJournals(params: BrowseJournalsParams = {}): Promise<BrowseJournalsResponse>`:
   - Serialises parameters into `URLSearchParams` (omitting empty or `"all"` values).
   - Calls `apiRequest<BrowseJournalsResponse>('/journals/browse?...', { method: 'GET' }, true)`.
2. `getJournalById(journalId: string | number): Promise<Journal>`:
   - Calls `apiRequest<Journal>(/journals/${journalId}, { method: 'GET' }, true)`.

---

## Phase 7 — UI Page Implementation (`BrowseJournalsPage.tsx`)

Create `frontend/src/pages/BrowseJournalsPage.tsx` with full feature set:

### 7.1 Page Layout & Header
- Title: **"Browse Journal Catalog"** with a badge displaying total count (e.g., `"{browseData.total} Verified Venues"`).
- Subtitle: Clear description of the 50 peer-reviewed catalog venues.
- Quick-action buttons:
  - **"My Shortlist (N)"**: displays live count of shortlisted journals from `AppContext` and navigates to `/compare`.
  - **"Semantic Matcher"**: quick link to `/finder` for title/abstract vector matching.

### 7.2 Search & Debounced Input
- Input with search icon, placeholder: `"Search by journal title, publisher, subject, ISSN, or keywords..."`.
- Clear button (`X`) visible when input is non-empty.
- 300ms debounce handler on input changes before triggering API request.
- Automatically resets `currentPage` to 1 on new search terms.

### 7.3 Multi-Criteria Filter Controls
- **Subject Area**: dropdown populated dynamically from `browseData.categories`.
- **Publisher**: dropdown populated dynamically from `browseData.publishers`.
- **Quartile**: dropdown with `All`, `Q1`, `Q2`, `Q3`, `Q4`.
- **Open Access**: dropdown with `All`, `Open access`, `Hybrid`, `Subscription`.
- **Sort By**: dropdown with `Title (A-Z)`, `CiteScore (Highest)`, `Impact Factor (Highest)`, `Acceptance Rate (Highest)`, `Review Speed (Fastest)`.
- **Sort Order**: toggle button (`ArrowUpDown`) switching between `asc` and `desc`.
- **Reset Filters**: button resetting all filters, search terms, and sort options to defaults.

### 7.4 View Mode Switcher
- Toggle buttons for **Grid View** (`LayoutGrid` icon) and **Table View** (`List` icon).

### 7.5 Journal Cards (Grid View)
Each card must display:
- **Header**: Quartile badge (color-coded: Q1 teal, Q2 blue, Q3 amber, Q4 slate) and Open Access badge.
- **Title**: clickable heading that opens the journal detail modal.
- **Metadata Subheader**: Publisher name, Subject Category, and ISSN.
- **Metric Badges Grid**:
  - CiteScore (or `"N/A"`)
  - Impact Factor (or `"N/A"`)
  - Review Speed (or `"N/A"`, formatted with `"w"` only if valid number)
  - Acceptance Rate (or `"N/A"`, formatted with `"%"` only if valid number)
- **Aims & Scope**: clamped 2-line preview.
- **Card Actions**:
  - **Shortlist Button**: toggles `toggleShortlistJournal(journal.id)` with bookmark icon and filled state if shortlisted.
  - **Compare Checkbox/Button**: toggles `toggleCompareJournal(journal.id)`, capped at 4 journals.
  - **"View Details"**: opens modal dialog.

### 7.6 Tabular View (Table View)
- Responsive table with columns: Journal & Publisher, Subject, Quartile, OA Type, CiteScore, Impact Factor, Review Time, Acceptance Rate, and Actions.
- Sticky header with clean hover highlights on rows.

### 7.7 Journal Profile Modal
Full-screen backdrop overlay dialog:
- Title, Publisher, ISSN, Subject Category.
- Quartile and Open Access badges.
- 4-column metric overview cards.
- Full un-truncated **Aims and Scope** text.
- **"Copy Scope"** button with a 2-second visual feedback (`Copied!` checkmark).
- **"Official Journal Homepage"** button opening `homepage_url` in an external tab (if available).
- Shortlist and Compare action buttons directly inside the modal footer.

### 7.8 Pagination Bar
- Results summary text: `"Showing X to Y of Z journals"`.
- Page size selector: `10`, `20`, `50` per page.
- Numeric pagination with smart truncation (first, last, current, and surrounding pages with ellipsis).
- Previous and Next buttons with proper disabled states on boundaries.

### 7.9 Loading, Empty & Error States
- **Loading State**: subtle skeleton cards or animated spinner during API requests.
- **Error State**: alert banner with error message and `"Try Again"` button.
- **Empty State**: illustration with `"No journals match your criteria"` and `"Reset All Filters"` CTA.

---

## Phase 8 — Navigation & Routing Integration

Integrate `/browse` across the application:

1. **`frontend/src/App.tsx`**:
   - Import `BrowseJournalsPage`.
   - Register route `<Route path="/browse" element={<BrowseJournalsPage />} />` under the main layout.
2. **`frontend/src/components/layout/Sidebar.tsx`**:
   - Add `{ label: 'Browse Journals', path: '/browse', icon: Library }` directly following `Projects` and preceding `Journal Finder`.
3. **`frontend/src/components/layout/TopBar.tsx`**:
   - Map route `path.startsWith('/browse')` to title string `'Browse Journals'`.
4. **`frontend/src/components/common/Button.tsx`**:
   - Ensure `whitespace-nowrap` and `shrink-0` classes are applied to prevent button text wrapping on compact toolbars.

---

## Phase 9 — Verification & Quality Assurance

Run the complete verification suite:

### 9.1 Automated Tests
- Backend test suite:
  ```powershell
  pytest -q
  ```
- Frontend typecheck and production build:
  ```powershell
  cd frontend
  npm run build
  ```
  Must build with 0 TypeScript or lint errors.

### 9.2 Manual End-to-End Verification
With backend and frontend running:
- [ ] Log in as a researcher; click **"Browse Journals"** in the sidebar. Verify `/browse` loads.
- [ ] Total count badge reflects catalog size (50 Verified Venues).
- [ ] Type in search box (e.g. `"IEEE"`, `"Software"`, or an ISSN); verify results filter within 300ms.
- [ ] Select a subject category; verify only matching journals render and total updates.
- [ ] Select quartile `"Q1"`; verify only Q1 journals render.
- [ ] Test sorting: sort by CiteScore (highest first); verify journals with `null` metrics sort to the end gracefully.
- [ ] Switch between Grid View and Table View; verify layout responsiveness.
- [ ] Click a journal card to open the Detail Modal; verify full Aims & Scope renders and **Copy Scope** copies text to clipboard.
- [ ] Click **Shortlist** on a journal; verify button reflects shortlisted state and header button `"My Shortlist (N)"` increments.
- [ ] Click **Compare** on up to 4 journals; navigate to `/compare` and verify journals are present in the matrix.
- [ ] Test pagination: change page size to 10, navigate to page 2, 3, etc.
- [ ] Enter an impossible search term (e.g. `"xyznonexistent"`); verify clean empty state and that clicking `"Reset All Filters"` restores catalog.

---

## Phase 10 — Documentation and Handoff

Update project documentation:

1. Update `backend/README.md`:
   - Document `GET /journals` and `GET /journals/browse` query parameters, sorting options, and response structure.
   - Document `GET /journals/{journal_id}` single journal profile endpoint.
2. Update root `README.md`:
   - Add **Browse Journals** (`/browse`) to the Implemented Screens & Features table.

---

## Final Acceptance Checklist

- [ ] `GET /journals` and `GET /journals/browse` endpoints are live, authenticated, and return paginated catalog data.
- [ ] `GET /journals/{id}` returns single journal profile or 404.
- [ ] Search works across title, publisher, subject, ISSN, and aims & scope.
- [ ] Faceted filters work for Subject Category, Publisher, Quartile, and Open Access Type.
- [ ] Dynamic facet lists (`categories`, `publishers`) are returned by the backend.
- [ ] Sorting supports title, CiteScore, Impact Factor, review speed, acceptance rate, and quartile with NULLS LAST.
- [ ] Dual view modes (Grid and Table) switch smoothly.
- [ ] Detail modal displays complete metadata, full aims & scope, and one-click copy.
- [ ] AppContext shortlist and compare actions integrate seamlessly without regressions on `/compare` or `/finder`.
- [ ] Missing metrics display as `"N/A"` — no fabricated values, `null weeks`, or `null%`.
- [ ] Backend tests in `test_journals.py` pass; `npm run build` passes with zero errors.

---

## Known limitations to mention in the report

- Catalog currently covers 50 verified computer science & interdisciplinary venues (designed to be expanded by re-running the data pipeline).
- Proprietary metrics (Clarivate Impact Factor, exact acceptance rates) are sparse in public databases and honestly displayed as N/A rather than estimated.
- Multi-journal comparison selection is constrained to a maximum of 4 venues to fit side-by-side display limits.

---

## Appendix — Suggested Antigravity prompts

**Phase 1 to 2: Prerequisites & Recon**
> Read `PublishAid_Browse_Journal_Plan.md`. Check Phases 1 and 2. Confirm database row counts, verify existing auth helpers, and review the frontend `Journal` type in `types/index.ts`. Report findings before making edits.

**Phase 3 to 5: Backend Schemas, Endpoints & Tests**
> Do Phases 3, 4, and 5 of `PublishAid_Browse_Journal_Plan.md`. Create `app/schemas/journal.py`, implement `app/api/journals.py`, mount the router in `app/main.py`, and write `tests/test_journals.py`. Run `pytest -q` and verify all tests pass.

**Phase 6 to 8: Frontend Client, Page & Navigation**
> Do Phases 6, 7, and 8 of `PublishAid_Browse_Journal_Plan.md`. Add `browseJournals` to `lib/api.ts`, implement `pages/BrowseJournalsPage.tsx` with Grid/Table views, detail modal, debounced search, and filters. Wire route into `App.tsx`, `Sidebar.tsx`, and `TopBar.tsx`.

**Phase 9 to 10: Verification & Docs**
> Do Phases 9 and 10 of `PublishAid_Browse_Journal_Plan.md`. Run `pytest -q` and `npm run build`. Perform end-to-end user testing against the acceptance checklist and update documentation.
