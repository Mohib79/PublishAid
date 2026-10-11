# PublishAid — AI-Driven Academic Publishing Platform

**PublishAid** is an end-to-end academic publishing support platform designed to assist researchers with manuscript preparation, venue discovery, author guidelines extraction, document conversion, and pre-submission compliance checking.

The project consists of:
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS (`frontend/`)
- **Backend**: FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL with pgvector (`backend/`)

---

## 🖥️ Implemented Screens & Features

| Screen / Feature | Route | Description |
|---|---|---|
| **Login** | `/login` | Live authentication with email & password, timing-safe error messaging, JWT session issuance, and password peek toggle. |
| **Sign Up** | `/signup` | Researcher registration, client-side validation, live 4-criteria password strength gauge, terms agreement, and direct dashboard onboarding. |
| **Dashboard** | `/dashboard` | Protected route. 4 live KPI metric cards, quick-action shortcuts, recent projects table with status pills, and recent activity feed. |
| **Workspace Manager** | `/projects` | Protected route. Search and filter active research workspaces, switch active draft, or initialize new manuscript folders. |
| **Journal Finder** | `/finder` | Protected route. Dual-pane layout: manuscript metadata / file dropzone on the left, ranked semantic recommendations on the right with match scores and quartile badges. |
| **Journal Comparison** | `/compare` | Protected route. Side-by-side comparative matrix evaluating up to 4 journals across Aims & Scope, Subject, CiteScore, Quartile, IF, Open Access, Review Speed, and Acceptance Rate. |
| **Guidelines & Templates** | `/guidelines` | Protected route. 3-step wizard: 1) Publisher & Smart Guidelines extraction, 2) Technical Specs & Typography fine-tuning, 3) Auto-generation of compilable LaTeX package (`.tex` + `.bib`). |
| **Manuscript Transformation** | `/transformation` | Protected route. Reformat existing manuscripts (`.docx` / `.tex`) to target journal rules with side-by-side single-to-double column preview and changes checklist. |
| **Document Converter** | `/converter` | Protected route. Bidirectional `Word ↔ LaTeX` converter with file drag-and-drop, preservation toggles, AST conversion progress, and ZIP download. |
| **Paper Summarizer** | `/summarizer` | Protected route. Summarize manuscripts into structured academic sections: Overview, Key Findings, Methods, and Limitations with Copy and Download actions. |
| **Compliance Checker** | `/compliance` | Protected route. Pre-submission audit against journal rules: Pass/Fail verdict, interactive checklist with actionable fixes, and Export PDF Report. |
| **Settings** | `/settings` | Protected route. Researcher profile configuration and ephemeral storage privacy policies. |

---

## ⚙️ Backend Setup (`backend/`)

### 1. Prerequisites
- **Python**: 3.10 or higher
- **PostgreSQL**: 16+ with `pgvector` extension (run locally or via Docker)
- **Docker Desktop** (optional, recommended for database)

### 2. Environment Configuration
From the `backend/` directory, create your `.env` file from the template:
```bash
cp .env.example .env
```
Ensure your database URL and settings are configured:
```ini
POSTGRES_USER=publishaid
POSTGRES_PASSWORD=publishaid_dev
POSTGRES_DB=publishaid
DATABASE_URL=postgresql+psycopg://publishaid:publishaid_dev@localhost:5433/publishaid
TEST_DATABASE_URL=postgresql+psycopg://publishaid:publishaid_dev@localhost:5433/publishaid_test
SECRET_KEY=publishaid_dev_secret_key_super_secure_random_key_12345
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### 3. Start Database (Docker)
```bash
docker compose up -d
```
Starts PostgreSQL 16 with `pgvector` mapped to host port `5433`.

### 4. Install Dependencies
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 5. Run Database Migrations
Apply Alembic migrations to create tables and drop legacy role structures:
```powershell
alembic upgrade head
```

### 6. Seed Development Data
Seed a demo researcher account (`researcher@publishaid.test` / `ResearcherPassword123!`), sample project, and sample guideline rules:
```powershell
python scripts/seed_dev_data.py
```

### 7. Run Test Suite
Run pytest against the test database:
```powershell
pytest -q
```

### 8. Run FastAPI Server
```powershell
uvicorn app.main:app --reload --port 8000
```
Interactive API docs will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 💻 Frontend Setup (`frontend/`)

### 1. Prerequisites
- **Node.js**: v18.0.0 or higher
- **npm**: v9.0.0 or higher

### 2. Environment Configuration
From the `frontend/` directory, create `.env`:
```bash
cp .env.example .env
```
Default configuration:
```ini
VITE_API_URL=http://localhost:8000
```

### 3. Install Dependencies & Run Development Server
```bash
cd frontend
npm install
npm run dev
```
Visit [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Production Build
```bash
npm run build
```
Typechecks via `tsc` and builds optimized static assets into `frontend/dist/`.

---

## 🔐 Authentication & Security Model

- **Single Role Model**: All users are Researchers; no administrative or guest access modes.
- **Password Security**: Argon2 password hashing (`pwdlib[argon2]`) with timing-attack mitigation on non-existent accounts during login.
- **Tokens**: Signed JWT bearer tokens with expiration (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Session Restoration**: Frontend checks stored token on load via `/auth/me` to seamlessly resume sessions without login flashes.
- **Route Guarding**: Unauthenticated visits to dashboard and workflow tools automatically redirect to `/login`.
