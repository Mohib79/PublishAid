# PublishAid — Journal Data Plan (Plan 1 of 2)

**Goal:** build a trustworthy catalog of 50 journals (extendable later), load it into PostgreSQL, and generate embeddings so the Journal Finder (Plan 2) has real data to match against.
**Audience:** Antigravity (implementation) and the three team members (manual data collection).
**Comes after:** database setup (`PublishAid_Database_Plan.md`) and ideally auth. **Comes before:** `PublishAid_Journal_Finder_Plan.md`.

---

## 0. Hard Rules

1. **Do NOT modify anything inside `frontend/`** in this plan. Reading it is allowed (Phase 1 only). This plan is backend, data and scripts only.
2. Work on a new branch `feature/journal-data`. All code goes under `backend/`. Do not edit root-level files.
3. **Never invent data.** If a value cannot be found from a real source, leave it empty (NULL). No guessed acceptance rates, review times, impact factors or scope texts. Empty is correct; fabricated is a bug.
4. **Never auto-accept an uncertain match.** If the script is not confident which OpenAlex record a journal maps to, it must put the journal in a review queue for a human.
5. Schema changes go through Alembic migrations only. Show each migration for review before applying.
6. Secrets (the OpenAlex API key) live in `backend/.env`, never in code or git.
7. The CSV files in `backend/seed/` are the **source of truth**. The app never calls OpenAlex at runtime. APIs are only used by build-time scripts.
8. Work one phase at a time, report results, and wait where the plan says STOP.

---

## 1. Decisions Already Made

| Topic | Decision |
|---|---|
| Size | 50 journals now (10 per publisher x 5 publishers), more added later by re-running the pipeline |
| Metadata source | OpenAlex API (free API key required) for title, publisher, ISSN, open-access status, APC, h-index, 2-year mean citedness, homepage |
| Ranking metrics | SCImago journal rankings CSV, **downloaded manually** by a team member (no scraping) |
| Aims and scope | **Collected manually** from each journal's official page. This is the text the embeddings are built from, so it is the most important field |
| Not available openly | Official Clarivate Impact Factor, acceptance rate, review time. Leave NULL; the UI shows N/A |
| Embedding model | SPECTER via sentence-transformers (768 dimensions), as in the FYP report |

### What each column will honestly contain

| Column | Source | Note |
|---|---|---|
| `journal_title`, `publisher`, `issn`, `openalex_id`, `homepage_url` | OpenAlex | verified by a human |
| `open_access_type` | OpenAlex `is_oa` | OpenAlex marks fully open-access journals. Most journals here are subscription or hybrid; hybrid cannot be detected automatically, so use a conservative value and let the team refine by hand |
| `apc_usd` | OpenAlex | often empty for subscription journals |
| `h_index`, `citedness_2yr` | OpenAlex | `citedness_2yr` is a 2-year mean citedness. It is similar in spirit to an impact factor but **not** the same thing |
| `sjr`, `quartile` | SCImago CSV | the quartile is the SCImago/SJR quartile, **not** Clarivate's. Document that |
| `citescore` | optional, Scopus source list | Phase 9 (optional). NULL otherwise |
| `impact_factor` | none | stays NULL (proprietary). Do not fill it from `citedness_2yr` |
| `review_weeks`, `acceptance_rate` | none | stay NULL |
| `subject_category` | manual, controlled list | see Phase 5 |
| `aims_and_scope`, `scope_source_url` | manual | see Phase 5 |

---

## 2. The 50 Journals (master list)

Create `backend/seed/journal_list.csv` with exactly these rows. Columns: `journal_title,publisher,issn,verify_note`. Leave `issn` empty (the script resolves it); the title text in parentheses is an abbreviation and must be **stripped before searching**, but kept in a separate `abbreviation` column if you want it.

```csv
journal_title,publisher,issn,verify_note
IEEE Transactions on Pattern Analysis and Machine Intelligence,IEEE,,abbr TPAMI
IEEE Transactions on Neural Networks and Learning Systems,IEEE,,
IEEE Transactions on Image Processing,IEEE,,
IEEE Transactions on Computers,IEEE,,
IEEE Transactions on Software Engineering,IEEE,,
IEEE Transactions on Knowledge and Data Engineering,IEEE,,
IEEE Transactions on Visualization and Computer Graphics,IEEE,,
IEEE Transactions on Mobile Computing,IEEE,,
IEEE Transactions on Dependable and Secure Computing,IEEE,,
IEEE Transactions on Information Forensics and Security,IEEE,,
Artificial Intelligence,Elsevier,,
Information Sciences,Elsevier,,
Pattern Recognition,Elsevier,,
Knowledge-Based Systems,Elsevier,,
Neurocomputing,Elsevier,,
Journal of Systems and Software,Elsevier,,
Computer Networks,Elsevier,,
Future Generation Computer Systems,Elsevier,,
Computer Vision and Image Understanding,Elsevier,,
Information Fusion,Elsevier,,
International Journal of Computer Vision,Springer,,abbr IJCV
Machine Learning,Springer,,
Artificial Intelligence Review,Springer,,
Autonomous Agents and Multi-Agent Systems,Springer,,
World Wide Web,Springer,,
Cluster Computing,Springer,,
Empirical Software Engineering,Springer,,
Neural Computing and Applications,Springer,,
Multimedia Tools and Applications,Springer,,
Computing,Springer,,VERIFY: confirm this journal is still active and still Springer
Journal of the ACM,ACM,,abbr JACM
Communications of the ACM,ACM,,abbr CACM; a magazine-style venue
ACM Computing Surveys,ACM,,abbr CSUR
ACM Transactions on Graphics,ACM,,abbr TOG
ACM Transactions on Database Systems,ACM,,abbr TODS
ACM Transactions on Computer Systems,ACM,,abbr TOCS
ACM Transactions on Software Engineering and Methodology,ACM,,abbr TOSEM
ACM Transactions on Information Systems,ACM,,abbr TOIS
ACM Transactions on Algorithms,ACM,,abbr TALG
ACM Transactions on Intelligent Systems and Technology,ACM,,abbr TIST
Computer Graphics Forum,Wiley,,
Software: Practice and Experience,Wiley,,
Computational Intelligence,Wiley,,
Expert Systems,Wiley,,
Concurrency and Computation: Practice and Experience,Wiley,,
Journal of Software: Evolution and Process,Wiley,,
Security and Privacy,Wiley,,
Wiley Interdisciplinary Reviews: Data Mining and Knowledge Discovery,Wiley,,
International Journal of Network Management,Wiley,,
Journal of Computer-Mediated Communication,Wiley,,VERIFY: believed to now be published by Oxford University Press, not Wiley
```

Two rows are flagged `VERIFY`. If the lookup shows a different publisher or a defunct journal, **do not silently correct it**: report it to the team, who decide whether to fix the publisher, swap the journal, or drop it.

---

## Phase 1 — Pre-flight and Read-Only Recon

1. Confirm the database is migrated (`alembic current`), the container is healthy, and `pytest -q` passes.
2. Confirm the existing `journals` table columns match the database plan.
3. **Read-only:** open the frontend's `Journal` type (look in `frontend/src/types`) and note the exact names and allowed values of fields such as `quartile`, `openAccessType`, `subjectCategory`. Report them. The seed data must use values the frontend already understands (for example the exact open-access label strings), so the later wiring is trivial.
4. Create the folder structure:

```
backend/
├── seed/
│   ├── journal_list.csv        # Phase 2 (the 50 rows above)
│   ├── scope_texts.csv         # Phase 5 (filled by humans)
│   ├── journals.csv            # Phase 6 (generated final dataset)
│   ├── review_queue.csv        # generated (uncertain matches)
│   ├── raw/                    # manually downloaded files (SCImago etc.)
│   └── cache/                  # raw API responses (git-ignored)
├── scripts/
│   ├── build_journal_dataset.py
│   ├── validate_journals.py
│   ├── seed_journals.py
│   ├── embed_journals.py
│   └── inspect_neighbors.py
```

5. Add `seed/cache/` to `backend/.gitignore`. Keep `seed/raw/*.csv` committed only if the file size is reasonable and the source's terms allow it; otherwise git-ignore it and document where to download it.
6. Add `OPENALEX_API_KEY=` to `backend/.env.example`. The team member who owns the key creates a free key from their OpenAlex account settings and puts it in their own `.env`.

STOP: report the frontend type findings, then continue.

---

## Phase 2 — Schema Additions (one migration)

Add these columns to `journals`, all nullable unless stated:

| Column | Type | Purpose |
|---|---|---|
| `openalex_id` | String(50), **unique** | stable external ID, enables re-syncing |
| `homepage_url` | String(500) | link out from the UI |
| `scope_source_url` | String(1000) | where the scope text was copied from (accountability) |
| `h_index` | Integer | from OpenAlex / SCImago |
| `apc_usd` | Integer | article processing charge |
| `sjr` | Float | SCImago journal rank score |
| `citedness_2yr` | Float | OpenAlex 2-year mean citedness |
| `embedding_hash` | String(64) | SHA-256 of the exact text that was embedded, to detect stale embeddings |
| `metadata_updated_at` | DateTime(tz) | last time metadata was refreshed |

Rules:
- Add CHECK constraints: `h_index >= 0`, `apc_usd >= 0`, `sjr >= 0`.
- Update the SQLAlchemy model and the schema tests accordingly.
- Show the migration, wait for approval, apply it, then verify `alembic downgrade -1` and `upgrade head` both work.
- Do **not** touch `impact_factor`, `review_weeks` or `acceptance_rate`; they remain NULL for now.

---

## Phase 3 — Build the Dataset from OpenAlex

Write `scripts/build_journal_dataset.py`. Before coding, read the OpenAlex API docs for the Sources endpoint (<https://developers.openalex.org>) and **inspect one real response** to confirm field names. Do not assume any field I list below exists exactly as written.

### Behaviour

1. Read `seed/journal_list.csv`. Strip parenthetical abbreviations from titles before searching.
2. For each journal, search OpenAlex Sources by title, restricted to journals. Look at the top few candidates.
3. **Matching rule (conservative):** accept a candidate automatically only if the normalized display name equals the normalized wanted title **and** the host organization name is consistent with the expected publisher (for example, "Institute of Electrical and Electronics Engineers" for IEEE, "Association for Computing Machinery" for ACM, "Springer Nature" or "Springer" for Springer, "Elsevier" and "Wiley" similarly; maintain a small alias map in code). Anything else goes to `seed/review_queue.csv` with the top candidates listed, and is **not** added to the dataset until a human resolves it by writing the chosen `issn` back into `journal_list.csv`.
4. When a journal has an ISSN in `journal_list.csv`, fetch it directly by ISSN instead of searching.
5. From each accepted record extract: OpenAlex ID, linking ISSN and all ISSNs, display name, host organization name, open-access flag, APC, homepage URL, h-index, 2-year mean citedness. Write `seed/journals_enriched.csv`.
6. **Cache** every raw API response as JSON under `seed/cache/openalex/` so re-runs do not hit the API again. Add a `--refresh` flag to bypass the cache.
7. Be gentle: sleep briefly between calls, retry transient errors with backoff, and stop with a clear message if the API key is missing or rejected.
8. Print a summary: matched automatically / sent to review queue / failed, plus any publisher mismatches discovered (these include the two `VERIFY` rows).

### Verification
- Run it. Expect most of the 50 to match; the review queue should be small.
- Show the team `review_queue.csv` and the publisher mismatch list.

STOP: the team resolves the review queue and the `VERIFY` rows. Then re-run until the queue is empty.

---

## Phase 4 — Merge SCImago Ranking Data

A team member **manually downloads** the SCImago journal rankings CSV (the "Journal Rankings" download on the SCImago site, one recent year) and saves it as `seed/raw/scimago_<year>.csv`. The script must not scrape the website.

1. Inspect the file first (delimiter, header names, how ISSNs are written; they are often several ISSNs per row without hyphens). Report the format before writing the merge code.
2. Normalize ISSNs on both sides (remove hyphens, uppercase) and match on any shared ISSN.
3. Pull `sjr`, the best quartile, and `h_index`. If OpenAlex and SCImago h-index differ, keep the SCImago value for `h_index` and document that choice.
4. Journals with no SCImago match keep NULL for these fields. Report how many matched.
5. Record the SCImago year used in `backend/README.md`. SCImago data should be credited as a source in the report.

---

## Phase 5 — Collect Aims and Scope (human task, with tooling)

This is the part that decides recommendation quality. Do not shortcut it.

### 5.1 Controlled subject list
Every journal gets exactly one `subject_category` from this list (the team may adjust it, but it must be fixed before collection starts):

```
Artificial Intelligence & Machine Learning
Computer Vision & Image Processing
Software Engineering
Security & Privacy
Networks & Distributed Systems
Data, Databases & Information Systems
Graphics & Visualization
Theory & Algorithms
General Computing & Reviews
```

### 5.2 Scope text rules (give these to the people collecting)
- Copy the text from the journal's **official** "Aims & Scope" or "About this journal" page.
- 80 to 300 words. If the page is longer, take the aims-and-scope part and skip editorial board, policies and author instructions.
- Plain text, no marketing slogans or navigation text, no copyright footer.
- Record the exact page URL in `scope_source_url`.
- Do not paraphrase or write it from memory. If a journal has no scope page, say so in the `notes` column and leave the text empty.

### 5.3 Template
The script generates `seed/scope_texts.csv` from the enriched list with these columns, one row per journal, scope fields empty:

```
openalex_id,journal_title,subject_category,aims_and_scope,scope_source_url,collected_by,collected_on,notes
```

### 5.4 Split the work
Split the 50 rows between the three team members (about 17 each, grouped by publisher so one person learns one publisher's site layout).

### 5.5 Validation helper
Write a check (part of `validate_journals.py`) that reports per-row problems in the scope CSV: empty text, under 80 words, over 400 words, missing URL, and **duplicate or near-duplicate texts** between two journals (a copy-paste mistake). The people collecting should run it themselves.

STOP: all 50 scopes collected and the check passes (or remaining gaps are documented).

---

## Phase 6 — Final Dataset and Validation

1. Merge enriched metadata + SCImago + scope texts into `seed/journals.csv` (script step, not manual).
2. Map `open_access_type` and `quartile` to the exact values the frontend expects (from the Phase 1 recon).
3. Write `scripts/validate_journals.py`. It must **fail with a non-zero exit code** if:
   - any required field is empty (`journal_title`, `publisher`, `issn`, `subject_category`, `aims_and_scope`)
   - `scope_source_url` is empty
   - an ISSN is duplicated or malformed
   - a numeric field is outside its allowed range
   - `quartile` is not one of Q1 to Q4 (or empty)
4. It must also **print a coverage report**: for each optional column, how many of the 50 are filled (`sjr`, `quartile`, `h_index`, `apc_usd`, `citedness_2yr`, `citescore`, `impact_factor`, `review_weeks`, `acceptance_rate`). The team will quote this coverage honestly in the report.

---

## Phase 7 — Seed the Database

Update `scripts/seed_journals.py` for the new columns:

- Reads `seed/journals.csv`; runs the validator first and refuses to proceed if it fails.
- **Upsert by `openalex_id`** (fall back to ISSN). Re-running must not create duplicates and must update changed fields.
- Single transaction; prints inserted / updated / unchanged counts.
- If a journal's `aims_and_scope` changed, set its `embedding` and `embedding_hash` to NULL so Phase 8 re-embeds it.
- Sets `metadata_updated_at`.

Verification: run twice; the second run reports 0 inserted and 0 updated. `SELECT count(*) FROM journals;` returns 50.

---

## Phase 8 — Generate Embeddings

Write `scripts/embed_journals.py` (heavy packages come from `requirements-embeddings.txt`; warn the user about the download size first).

1. Load the SPECTER checkpoint through sentence-transformers. **Assert the output dimension is 768** and abort otherwise. Put the model name in one config constant shared with the future matching service, so the query side and the journal side can never use different models.
2. Text to embed per journal: `journal_title + ". " + aims_and_scope`, built by one function `build_journal_text(journal)` in a shared module (the matching service will import the same module).
3. Compute `embedding_hash = sha256(text)`. Embed only rows where `embedding IS NULL` or `embedding_hash` differs from the current text hash. Add `--force` to re-embed everything and `--limit N` for quick tests.
4. Batch (16 to 32 per batch), commit per batch, store `embedding_model`.
5. Print progress and total time.

Verification: `SELECT count(*) FROM journals WHERE embedding IS NULL;` returns 0.

---

## Phase 9 — Sanity Checks (before Plan 2)

1. **Neighbour inspection.** Write `scripts/inspect_neighbors.py`: for each journal print its 3 nearest neighbouring journals by cosine similarity. Review by eye. Expect sensible clusters (computer vision journals near each other, software engineering journals near each other). Odd neighbours usually mean a bad or too-short scope text; fix the text and re-embed.
2. **Outliers.** Journal of Computer-Mediated Communication is far from the rest of the list and Communications of the ACM is broad. Note how they behave; they are useful edge cases for the later evaluation.
3. **Optional: CiteScore.** If a team member can download Elsevier's Scopus source list (check that it is currently available for free), merge `citescore` by ISSN the same way as SCImago. Otherwise leave it NULL and decide with the team what the frontend should show for the "CiteScore" field.

---

## Phase 10 — Documentation

Update `backend/README.md` with:
- the exact pipeline commands in order,
- the data sources and their caveats (quartile is SJR-based, `citedness_2yr` is not an impact factor, which fields are empty and why),
- how to add new journals later (append to `journal_list.csv`, run the build script, resolve the review queue, collect scope text, validate, seed, embed),
- the SCImago year and the date the data was built.

---

## Final Acceptance Checklist

- [ ] Migration applied; model and tests updated; downgrade/upgrade round-trips.
- [ ] 50 journals in `journal_list.csv`; review queue empty; the two `VERIFY` rows resolved and documented.
- [ ] All 50 have a real `aims_and_scope` (80 to 300 words) and a `scope_source_url`.
- [ ] `validate_journals.py` passes and the coverage report is saved.
- [ ] `seed_journals.py` is idempotent (second run changes nothing); DB has 50 rows.
- [ ] All 50 rows have an embedding with the correct `embedding_model` and `embedding_hash`.
- [ ] Neighbour inspection reviewed by a human; obvious bad scope texts fixed.
- [ ] No secrets committed; `git diff --stat main -- frontend/` prints nothing.
- [ ] `pytest -q` is green.

---

## Appendix — Suggested Antigravity prompts

**Phases 1 to 2**
> Read `PublishAid_Journal_Data_Plan.md`. Do Phases 1 and 2 only. Do not edit anything in `frontend/`. Report what you found in the frontend `Journal` type, show me the migration before applying it, then stop.

**Phases 3 to 4**
> Do Phases 3 and 4. Inspect a real OpenAlex response before writing the parser. Never auto-accept an uncertain match. Show me the review queue and the SCImago file format, then stop.

**Phases 6 to 8**
> Do Phases 6 to 8. The validator must fail loudly. Do not invent any missing data; leave it empty. Report coverage numbers and embedding counts.

**Phase 9 to 10**
> Do Phases 9 and 10, then run the Final Acceptance Checklist and report each item as pass or fail.
