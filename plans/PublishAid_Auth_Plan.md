# PublishAid — Authentication Plan (Plan 0)

**Goal:** make login, signup and session restore work for real: password hashing, JWT tokens, protected routes, and the existing React pages wired to the backend.
**Audience:** Antigravity (implementation) and the team (review).
**Requires first:** the database is set up and migrated (`PublishAid_Database_Plan.md`).
**Comes before:** `PublishAid_Journal_Data_Plan.md` and `PublishAid_Journal_Finder_Plan.md`.

Order of all plans: Database -> **Auth (this file)** -> Journal Data -> Journal Finder.

---

## 0. Hard Rules

1. Work on a new branch `feature/auth`. Commit the backend and the frontend as **two separate commits**.
2. **Frontend edits are allowed, but only to the files listed in Part B.** Do not restyle anything, do not change layout, colors or copy beyond what is listed, and do not touch any other page.
3. Do Part A (backend) completely, verify it, and **STOP for approval** before starting Part B.
4. Never commit secrets. `SECRET_KEY` lives in `backend/.env`; only `.env.example` is committed.
5. Schema changes go through Alembic migrations. Show the migration before applying it.
6. Never store or log plain-text passwords. Never return `password_hash` in any response.

---

## 1. Decisions Already Made

| Topic | Decision |
|---|---|
| Account types | **One kind of account: Researcher.** No admin, no guest mode. A new visitor must register first |
| Route protection | Every endpoint except register, login and health requires a valid token |
| `role` column | Removed from `users` entirely (model, migration, seed script, tests) |
| `plan` ("Pro plan") | Not stored in the database. Stays a frontend-only constant for now; the team should remove the label before the demo if no plans exist in the report |
| `avatarInitials` | Not stored. Computed in the frontend from `fullName` |
| Password hashing | Argon2 via `pwdlib` |
| Tokens | JWT access token, short expiry (default 60 minutes), `PyJWT`. No refresh tokens (future work) |
| Token storage in the browser | `localStorage` with an `Authorization: Bearer` header. Known XSS tradeoff, accepted for this project; add a code comment saying so |
| API style | JSON in and out, **camelCase** to match the frontend (`fullName`, `accessToken`) |
| User ID | Integer in the database, returned as a **string** in the API (the frontend type uses a string) |
| Forgot password | Left as the existing alert. Needs email sending; future work |

---

## What the existing pages do today (so the agent doesn't guess)

- `LoginPage` ignores what is typed. It prefills a demo email and a fake password string, waits 600 ms, and always signs in "Dr. Maya Chen".
- `SignUpPage` does the same with the entered values. It sends nothing anywhere, never checks that the two passwords match, shows a static "Strong" strength meter that is always on, and includes a "Your role" dropdown (Researcher / Administrator).
- The user exists only in React context (`setUser`), so a page refresh logs the user out.
- Neither page has anywhere to show an error.

Form fields: login sends `email` and `password`; signup has `fullName`, `email`, `password`, `confirmPassword`, `role`, `agreeTerms`. The app's user object currently is `{ id, fullName, email, role, plan, avatarInitials }`.

---

# PART A — BACKEND

## Phase A1 — Pre-flight

- [ ] `alembic current` shows head; the database container is healthy; `pytest -q` is green.
- [ ] A FastAPI app entry point exists (create `app/main.py` if the database plan did not).
- [ ] Report whether the initial migration has already been applied to the dev database. This decides how `role` is removed in Phase A2.

## Phase A2 — Remove `role` from users

- If the initial migration was **never applied** anywhere shared: edit the initial migration and model.
- If it **was applied** (any teammate's database): add a **new** migration that drops the `role` column and its CHECK constraint. Never edit an applied migration.
- Update the SQLAlchemy model, `scripts/seed_dev_data.py` (remove the admin user and any role usage) and the schema tests.
- Show the migration, wait for approval, apply it, and verify `downgrade -1` then `upgrade head`.

## Phase A3 — Dependencies and Settings

1. Add to `requirements.txt`: `pwdlib[argon2]` and `PyJWT`.
2. Settings in `app/core/config.py`, loaded from `.env`:
   - `SECRET_KEY` (required; the app must **fail at startup** if missing or empty)
   - `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60)
   - `CORS_ORIGINS` (default `http://localhost:3000`; allow a comma-separated list)
3. Add all three to `.env.example`, with a comment on how to generate a strong key (for example `python -c "import secrets; print(secrets.token_urlsafe(48))"`).

## Phase A4 — Security Helpers

`app/core/security.py`:

- `hash_password(password)` and `verify_password(password, hash)` using Argon2.
- `create_access_token(user_id)`: JWT with `sub` (the user ID **as a string**, PyJWT requires a string subject), `iat` and `exp`.
- `decode_access_token(token)`: returns the user ID or raises a clear error for invalid or expired tokens.
- A precomputed **dummy hash** used for login attempts against unknown emails, so that "unknown user" and "wrong password" take similar time.

## Phase A5 — Schemas (Pydantic v2)

All schemas use a camelCase alias generator with `populate_by_name=True`.

| Schema | Fields and rules |
|---|---|
| `RegisterRequest` | `fullName` (trimmed, 1 to 150 chars), `email` (valid email), `password` (8 to 128 chars). **Do not trim the password.** No `role` field; unknown fields are ignored |
| `LoginRequest` | `email`, `password` |
| `UserOut` | `id` (string), `fullName`, `email` |
| `AuthResponse` | `accessToken`, `tokenType` (`"bearer"`), `user` (`UserOut`) |

`password_hash` must never appear in any output schema.

## Phase A6 — Routes and Dependency

Under `/auth`:

- **`POST /auth/register`**
  - Trim and lowercase the email.
  - If the email already exists (case-insensitively), return **409** with "An account with this email already exists".
  - Create the user, hash the password, return `AuthResponse` (the frontend goes straight to the dashboard after signup).
  - Handle the race where two simultaneous requests pass the existence check: catch the unique-constraint error and return the same 409.
- **`POST /auth/login`**
  - Body is **plain JSON**, not FastAPI's OAuth2 form format (the pages send JSON).
  - Trim and lowercase the email.
  - Any failure (unknown email or wrong password) returns **401** with the identical message "Invalid email or password".
  - Use the dummy hash when the user does not exist.
- **`GET /auth/me`**: requires a Bearer token and returns `UserOut`.

`app/api/deps.py`: a reusable `get_current_user` dependency. It returns 401 for a missing, malformed, invalid or expired token, and 401 if the token is valid but the user no longer exists. All future protected routes use it.

## Phase A7 — App Setup

`app/main.py`:

- Create the app and include the auth router.
- `CORSMiddleware` using `CORS_ORIGINS`; `allow_credentials=False`; allowed headers `Authorization` and `Content-Type`; allowed methods GET, POST, PUT, DELETE, OPTIONS.
- `GET /health` (public) that returns a simple OK. Optionally include a database check.

## Phase A8 — Seed Script

Update `scripts/seed_dev_data.py`: the demo researcher gets a **real Argon2 hash** from `hash_password` (use a documented dev password that is only for local use), and the script refuses to run when `APP_ENV=production`.

## Phase A9 — Backend Tests

Against the test database (`pytest`):

- register succeeds and returns a token and user;
- registering the same email again returns 409, including with different letter case and surrounding spaces;
- password shorter than 8 returns 422; password longer than 128 returns 422;
- invalid email returns 422;
- login succeeds; wrong password and unknown email both return 401 with **identical** bodies;
- `/auth/me` works with a valid token, and returns 401 for a missing token, a garbage token, and an expired token (create one with a negative expiry);
- a token for a deleted user returns 401;
- no response ever contains `password`, `passwordHash` or `password_hash`;
- an extra `role` field in the register body is ignored (no error, no effect);
- a protected placeholder route returns 401 without a token.

## Phase A10 — Backend Verification

- [ ] `uvicorn app.main:app --reload` starts; startup **fails clearly** if `SECRET_KEY` is removed.
- [ ] Register, login and `/auth/me` all work from the interactive API docs page (`/docs`), including the "Authorize" flow or by pasting the token.
- [ ] `pytest -q` is green.
- [ ] `git diff --stat main -- frontend/` prints nothing.

### STOP. Report results and wait for approval before Part B.

---

# PART B — FRONTEND

**Files you may modify:** `LoginPage`, `SignUpPage`, `context/AppContext`, the `types` file (user type and `UserRole`), and any route-guard or logout/user-menu component if they exist.
**Files you may create:** one small API helper (for example `src/lib/api.ts`) and `frontend/.env.example`.
Nothing else.

## Phase B1 — Read-Only Recon (STOP and report)

Before editing anything, report:

1. How routes are currently protected (if at all) and where the app decides what to show when there is no user.
2. Every use of `setUser`, `user.role`, `user.plan`, `user.avatarInitials` and `UserRole` across the whole frontend, including pages you will not edit (Settings, Dashboard, header/sidebar).
3. Whether a logout or user-menu control already exists.
4. Whether a toast or notification component exists.

Propose the exact list of files you will change. Wait for approval.

## Phase B2 — API Helper

- Base URL from `import.meta.env.VITE_API_URL` (default `http://localhost:8000`).
- Functions `register()`, `login()`, `getMe()`.
- Attaches `Authorization: Bearer <token>` when a token is stored.
- Parses the error `detail` from failed responses into a readable message; handles validation errors (422) by showing the first useful message, and network failures with a friendly "could not reach the server" message.
- On a 401 from a protected call, clears the stored token.
- Token is stored in `localStorage` under one key. Add a short code comment noting the XSS tradeoff was accepted for this project.

## Phase B3 — Types

- Remove `role` from the user type and delete `UserRole` if nothing else needs it (the recon tells you).
- The user type becomes `{ id: string; fullName: string; email: string }`.
- Provide one shared helper `getInitials(fullName)` instead of storing initials. Replace usages of `avatarInitials`.
- `plan`: do not send or receive it. Where it is displayed, keep it as a frontend-only constant and **list those places in your report**.

## Phase B4 — AppContext

- Keep the existing `setUser` API so other pages are unaffected.
- Add `logout()` (clear token and user) and an `isAuthLoading` flag.
- On app load, if a token exists, call `getMe()` to restore the session; if it fails, clear the token.
- Protected routes must **wait for `isAuthLoading` to finish**, so a page refresh does not flash the login screen or log the user out.
- If there is currently no route guard, add the smallest one that redirects unauthenticated users to `/login` for all pages except `/login` and `/signup`.

## Phase B5 — LoginPage

- Remove the prefilled demo email and the fake password string; start empty.
- Replace the `setTimeout` mock with a real `login()` call; store the token, set the user, navigate to `/dashboard`.
- Show server errors (for example "Invalid email or password") in an **inline error message above the button**, in the existing red or slate text style and spacing.
- Keep the loading state on the button.
- Leave "Forgot password?" exactly as it is.

## Phase B6 — SignUpPage

- Remove all prefilled values; start with the terms checkbox **unchecked**.
- Remove the "Your role" select and its state completely.
- Client-side checks before submitting: passwords match; password at least 8 characters; terms agreed. Show them inline, not as `alert()`.
- Make the strength meter **real**, computed from the actual password (length of 8 or more, has a number, has a symbol, has both upper and lower case): the number of filled bars and the label must follow it, and the hint text must state the real rule. The backend only enforces length; the meter is guidance.
- Call `register()` with only `{ fullName, email, password }`; store the token, set the user, navigate to `/dashboard`.
- Show "An account with this email already exists" (from the 409) inline.

## Phase B7 — Logout

If the existing UI already has a user menu or sign-out control, wire it to `logout()` and navigate to `/login`. If there is none, **do not invent a design**; just report it so the team can decide.

## Phase B8 — Config

Create `frontend/.env.example` containing `VITE_API_URL=http://localhost:8000`. Do not change other config.

## Phase B9 — Do Not

- Do not change layout, colors or copy beyond the items above.
- Do not touch other pages. They keep their mock data.
- Do not implement password reset, refresh tokens, or social login.

## Phase B10 — Frontend Verification

With the backend running:

- [ ] `npm run build` passes with no TypeScript errors.
- [ ] Sign up with a new email: lands on `/dashboard`.
- [ ] Refresh the page: still logged in, no flash of the login screen.
- [ ] Logout (if a control exists): back at `/login`; protected pages redirect to `/login`.
- [ ] Log in again with the same account.
- [ ] Wrong password shows the inline "Invalid email or password".
- [ ] Signing up again with the same email shows the 409 message.
- [ ] Mismatched passwords, short passwords and unchecked terms are blocked client-side with inline messages.
- [ ] Stopping the backend shows the friendly "could not reach the server" message.
- [ ] `git diff --stat main -- frontend/` lists **only** the allowed files.

---

## Final Acceptance Checklist

- [ ] `role` is gone from the database, model, seed script, tests and frontend types.
- [ ] Passwords are Argon2-hashed; no response exposes a hash.
- [ ] Login failures return one identical generic message.
- [ ] Tokens expire; expired, malformed and missing tokens return 401.
- [ ] `SECRET_KEY` is required and not committed.
- [ ] CORS allows the frontend origin only.
- [ ] Signup, login, session restore and (if present) logout work end to end.
- [ ] Only the allowed frontend files changed; backend tests green; build passes.

## Known limitations to mention in the report

No password reset, no email verification, no refresh tokens, no rate limiting on login attempts, and tokens in `localStorage` (XSS tradeoff). All are reasonable future work for an FYP.

---

## Appendix — Suggested Antigravity prompts

**Part A**
> Read `PublishAid_Auth_Plan.md`. Do Part A (backend) only, phases A1 to A10. Do not touch `frontend/`. Show me the migration before applying it. When finished, report the verification checklist and stop.

**Part B, recon**
> Do Phase B1 only. Do not edit any file. Report what you found and which files you propose to change, then stop.

**Part B, implementation**
> Do Phases B2 to B10, only modifying the files I approved. Run the frontend verification list and the Final Acceptance Checklist and report each item as pass or fail.
