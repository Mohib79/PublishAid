# PublishAid — Frontend Implementation

**PublishAid** is an AI-driven, end-to-end academic publishing support platform designed to assist researchers with manuscript preparation, venue discovery, author guidelines extraction, document conversion, and pre-submission compliance checking.

This implementation faithfully reproduces all screens and reusable UI specifications from the **Project Proposal & Final Project Report (FAST NUCES Lahore)** and the high-resolution Figma design tokens located in `antigravity/`.

---

## 🎨 Design System & Foundations
* **Color Palette:**
  - **Deep Teal (Primary):** `#0F766E` (Active: `#0D5E4B`, `#0B4638`)
  - **Soft Mint (Accent/Highlights):** `#CCFBF1` (Border: `#99F6E4`)
  - **Dark Navy (Headings/Body):** `#14283D`
  - **Canvas (Background):** `#F6F8FB`
  - **Cards & Surfaces:** `#FFFFFF` with `rounded-2xl` (16px border-radius) and subtle borders (`border-slate-200/80`)
* **Typography:** Inter (8px rhythm, strict hierarchy matching Figure 4.1 - 4.10)
* **Button Standards:** 42px height, 8px border radius, clear hover/focus/active micro-interactions
* **Top Bar:** 72px height with breadcrumb navigation, settings, and researcher profile indicator
* **Sidebar:** 260px expanded / 78px collapsed responsive modes with active mint pill indicators

---

## 🖥️ Implemented Screens & Features

| Screen / Feature | Route | Report Reference | Description |
|---|---|---|---|
| **Login** | `/login` | Figure 4.1 (`Log_in.png`) | Split layout with credential authentication, password peek toggle, and brand hero value proposition |
| **Sign Up** | `/signup` | Figure 4.2 (`Sign_up.png`) | Full registration flow, password strength gauge, role selection (`Researcher` / `Administrator`), and terms agreement |
| **Dashboard** | `/dashboard` | Figure 4.3 (`Dashboard.png`) | 4 live KPI metric cards, quick-action shortcuts, recent projects table with status pills, and recent activity feed |
| **Workspace Manager** | `/projects` | Table 4.3 | Search and filter active research workspaces, switch active draft, or initialize new manuscript folders |
| **Journal Finder** | `/finder` | Figure 4.4 (`Journal_Finder___Results.png`) | Dual-pane layout: manuscript metadata / file dropzone on the left, ranked semantic journal recommendations on the right with match scores, quartile badges, and shortlisting |
| **Journal Comparison** | `/compare` | Figure 4.5 (`Journal_Comparison.png`) | Side-by-side comparative matrix evaluating up to 4 journals across Aims & Scope, Subject, CiteScore, Quartile, IF, Open Access, Review Speed, and Acceptance Rate with mint highlights for top values |
| **Guidelines & Templates** | `/guidelines` | Figure 4.6 & Tech Specs | 3-step wizard: 1) Publisher & Smart Guidelines AI extraction, 2) Technical Specs & Typography fine-tuning, 3) Auto-generation of compilable LaTeX package (`.tex` + `.bib`) |
| **Manuscript Transformation** | `/transformation` | Figure 4.7 (`Manuscript_Transformation.png`) | Reformat existing manuscripts (`.docx` / `.tex`) to target journal rules with side-by-side single-to-double column preview and changes checklist |
| **Document Converter** | `/converter` | Figure 4.8 (`Document_Converter___Complete.png`) | Bidirectional `Word ↔ LaTeX` converter with file drag-and-drop, preservation toggles, AST conversion progress, and ZIP download |
| **Paper Summarizer** | `/summarizer` | Figure 4.9 (`Paper_Summarizer.png`) | Summarize manuscripts into structured academic sections: Overview, Key Findings, Methods, and Limitations with Copy and Download actions |
| **Compliance Checker** | `/compliance` | Figure 4.10 (`Compliance_Checker.png`) | Pre-submission audit against journal rules: Pass/Fail verdict, interactive checklist with actionable fixes, and Export PDF Report |
| **Settings** | `/settings` | Section 5.4.3 | Researcher profile configuration and ephemeral storage privacy policies |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Node.js**: v18.0.0 or higher (v22 installed)
- **npm**: v9.0.0 or higher

### 2. Run the Development Server
From the project root:
```bash
npm run dev
```
Or directly from the `frontend` folder:
```bash
cd frontend
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) in your browser.

### 3. Production Build
```bash
npm run build
```
Generates optimized, production-ready static assets in `frontend/dist/`.
