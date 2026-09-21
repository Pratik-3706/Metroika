# Metroika — Legal Metrology Compliance Checker

> **SIH 2026 · Problem ID: SIH26034** — Software System to check compliance of Packaged Commodities under Legal Metrology (Packaged Commodities) Rules, 2011

Metroika is an automated compliance verification platform designed for India's Legal Metrology standards and FSSAI packaging norms. The system combines local neural OCR, optical barcode/QR decoding, an expert 22-clause deterministic statutory rules engine, and optional multimodal AI vision verification to generate court-admissible audit dossiers and enforcement dashboards.

---

## ⚡ Key Features

- **Multi-Angle Packaging Intake** — Ingest front, back, nutrition table, and side panel imagery with automated EXIF orientation correction and CLAHE contrast enhancement.
- **Neural OCR Engine (PaddleOCR v3.7)** — PP-OCRv5 Server Detection, PP-LCNet 90°/180°/270° angle classification, and bilingual text recognition (Devanagari Hindi & Latin English) with bounding-box geometry extraction.
- **Optical Barcode & QR Decoding** — Optical extraction via `pyzbar` and OpenCV for EAN-13, UPC-A, Code128, and QR codes, including GS1-890 Made-in-India country prefix validation.
- **Deterministic 22-Clause Statutory Rules Engine** — Codified regulatory verification for:
  - **Rule 6(1)(a)**: Complete Manufacturer/Packer/Importer Name & Address
  - **Rule 6(1)(b)**: Generic / Common Product Name
  - **Rule 6(1)(c)**: Net Quantity in standard SI units (g, kg, ml, l, m, N)
  - **Rule 6(1)(d)**: Month & Year of manufacture, packing, or import (MM/YYYY format)
  - **Rule 6(1)(e)**: Maximum Retail Price (MRP) syntax (`MRP Rs. XX.XX (incl. of all taxes)`)
  - **Rule 6(1)(f)**: Complete Consumer Care details (Name, Address, Phone, Email)
  - **Rule 6(1)(g)**: Country of Origin declaration
  - **Rule 6(2)**: Unit Sale Price (USP) computation & declaration (per g, kg, ml, l, or unit)
  - **Rule 6(3)**: Language compliance (English and/or Devanagari Hindi)
  - **Rule 7 & Table I**: Minimum font height compliance relative to Principal Display Panel (PDP) area
  - **Rule 8**: Principal Display Panel placement verification
  - **Drugs & Cosmetics / Pharma Regime**: Drug manufacturing license (`Mfg. Lic. No.`), active formulation/composition, dosage directions, schedule classifications (Schedule H/G/X), and mandatory warning statements
  - **FSSAI & Traceability**: 14-digit FSSAI license syntax & barcode presence
- **Statutory Penalty Mapping** — Automatic violation-to-penalty calculation based on Section 36(1) of the Legal Metrology Act, 2009 (1st Offence: up to ₹25,000 | 2nd Offence: up to ₹50,000).
- **Multimodal AI Vision Verifier (Optional Fallback)** — Cloud multimodal VLM (`gemini-2.5-flash` / `kimi-k2.5`) to cross-validate distorted, curved, or low-contrast packaging declarations. System remains 100% operational offline/locally without external AI.
- **Role-Based Access Control (RBAC)** — Secure standard-library PBKDF2-HMAC-SHA256 authentication supporting `Inspector` (Enforcement Officers), `Merchant` (Brand Compliance), and `Public` (Consumers).
- **Court-Admissible PDF Dossiers** — ReportLab engine creates color-coded PDF reports with embedded bounding-box crop visuals, statutory rule citations, and penalty breakdowns.
- **Enforcement Dashboard & Analytics** — Interactive Chart.js visualizer showing compliance scores, common violation distributions, and product audit histories.

---

## 🛠️ Architecture & Tech Stack

| Layer | Technologies |
|---|---|
| **Backend Framework** | Python 3.10 / 3.11, FastAPI, Pydantic Settings (v2), Uvicorn ASGI |
| **Database & ORM** | SQLAlchemy 2.0 (asyncio), SQLite (aiosqlite) / PostgreSQL |
| **Neural OCR Engine** | PaddleOCR v3.7, PP-OCR Server Det/Rec, PP-LCNet Angle Classifier |
| **Barcode & Vision** | pyzbar, OpenCV (`opencv-python-headless`), Pillow (PIL), qrcode |
| **Optional AI Verifier** | OpenAI Python SDK (compatible with Gemini 2.5 Flash / Kimi-k2.5 via OpenAI-compatible endpoints) |
| **PDF Reporting** | ReportLab 4.x (Dynamic tabular layout, bounding-box evidence flowables) |
| **Frontend** | Vanilla HTML5 / CSS3 / JavaScript SPA (Architectural Minimalist Editorial UI), Chart.js |
| **Security & Auth** | PBKDF2-HMAC-SHA256 password hashing, HMAC-SHA256 signed bearer tokens, RBAC |

---

## 🚀 Quick Start & Installation

### Option A: One-Click Automated Setup (Windows)

1. Clone repository:
   ```bash
   git clone https://github.com/Pratik-3706/Metroika.git
   cd Metroika
   ```
2. Run the automated installer:
   ```cmd
   setup.bat
   ```
   *This checks for Python 3.10/3.11, creates the virtual environment, installs core dependencies, detects hardware (CPU vs CUDA GPU for PaddlePaddle), and pre-downloads the OCR models.*
3. Launch both backend and frontend servers:
   ```cmd
   start.bat
   ```
   *The application will automatically open at `http://localhost:3000` with the API on `http://localhost:8000`.*

---

### Option B: Manual Setup

#### 1. Backend Setup
```bash
cd backend

# Create and activate virtual environment (Python 3.10 or 3.11 recommended)
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# Upgrade pip & install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run hardware detection and install PaddlePaddle (CPU or GPU)
python install_env.py

# Pre-cache multilingual OCR models
python download_models.py
```

#### 2. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env   # On Windows: copy .env.example .env
```
*(Optional) If you wish to use the multimodal AI verifier fallback, set your API key in `backend/.env`:*
```env
AICREDITS_API_KEY=your_api_key_here
AICREDITS_BASE_URL=https://aicredits.in/v1
VISION_MODEL=moonshotai/kimi-k2.5
```
> **Note**: AI verification is completely optional. If no API key is provided, Metroika automatically runs in 100% deterministic local mode using PaddleOCR and the statutory rules engine.

#### 3. Run Backend
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation: `http://localhost:8000/docs`

#### 4. Run Frontend
In a new terminal window:
```bash
cd frontend
python -m http.server 3000
```
Open your browser and navigate to: `http://localhost:3000`

---

## 👥 Default RBAC Accounts

Metroika automatically seeds the database with three default role-based accounts:

| Role | Username | Default Password | Permissions |
|---|---|---|---|
| **Inspector** | `inspector` | `Inspector@2026!` | Full regulatory enforcement access, audit log viewing, dossier downloads, compliance overrides |
| **Merchant** | `merchant` | `Merchant@2026!` | Pre-market packaging validation, re-test submission, corrective action report access |
| **Public** | `public` | `Public@2026!` | Consumer verification, barcode lookups, basic compliance scoring |

---

## 📋 Codified Statutory Rules

| Rule ID | Statutory Reference | Verification Scope | Severity |
|---|---|---|---|
| `R6_1_A_NAME` | Rule 6(1)(a) | Manufacturer, Packer, or Importer Name declaration | **Critical** |
| `R6_1_A_ADDR` | Rule 6(1)(a) | Complete postal address with city, state, and pin code | **Critical** |
| `R6_1_B` | Rule 6(1)(b) | Generic or common name of the commodity | **High** |
| `R6_1_C` | Rule 6(1)(c) | Net quantity in legal standard units (g, kg, ml, l, N) | **Critical** |
| `R6_1_D` | Rule 6(1)(d) | Month and year of manufacture, packing, or import (MM/YYYY) | **High** |
| `R6_1_E` | Rule 6(1)(e) | Maximum Retail Price declared as `MRP Rs. XX (incl. of all taxes)` | **Critical** |
| `R6_1_F` | Rule 6(1)(f) | Consumer complaint contact details (Name, Address, Tel, Email) | **High** |
| `R6_1_G` | Rule 6(1)(g) | Country of origin on imported packaged commodities | **High** |
| `R6_UNIT` | Rule 6(2) | Unit Sale Price (USP) for items exceeding 1g or 1ml | **High** |
| `R6_LANG` | Rule 6(3) | Declarations in English or Hindi (Devanagari script) | **Medium** |
| `R7_FONT` | Rule 7, Table I | Minimum numeral & letter height vs Principal Display Panel area | **Medium** |
| `R8_PDP` | Rule 8 | Presence of statutory declarations on Principal Display Panel | **Medium** |
| `BARCODE` | Standard | Optical EAN-13, UPC-A, or QR code detection & GS1-890 India match | **Low** |
| `DRUG_LIC` | Drugs & Cosmetics | Drug Manufacturing License Number (`Mfg. Lic. No.`) | **High** |
| `COMP_1` | Drugs & Cosmetics | Quantitative active formulation & ingredient composition | **High** |
| `DOSE_1` | Drugs & Cosmetics | Dosage instructions or physician directive | **High** |
| `WARN_1` | Drugs & Cosmetics | Mandatory statutory caution & contraindication warnings | **Medium** |
| `SCHED_1` | Drugs & Cosmetics | Schedule H / Schedule X / prescription warning boxes | **Medium** |

---

## 📁 Repository Structure

```
Metroika/
├── backend/
│   ├── app/
│   │   ├── rules/            # Codified statutory rules (metrology, penalties, font tables)
│   │   ├── services/         # Core engines: compliance, ocr, barcode, vision, report_gen
│   │   ├── routers/          # FastAPI API routes (analysis, products, reports, dashboard, auth)
│   │   ├── auth.py           # Cryptographic PBKDF2-HMAC RBAC service
│   │   ├── database.py       # SQLAlchemy async ORM models & database initialization
│   │   ├── config.py         # Pydantic v2 application configuration
│   │   └── main.py           # FastAPI entrypoint, lifespan, and CORS middleware
│   ├── download_models.py    # Pre-cache script for PaddleOCR detection & recognition models
│   ├── install_env.py        # Hardware detection script for CUDA vs CPU PaddlePaddle
│   ├── requirements.txt      # Core backend Python dependencies
│   └── .env.example          # Environment variable template
├── frontend/
│   ├── css/
│   │   └── styles.css        # Minimalist Architectural & Editorial Design System
│   ├── js/                   # Frontend SPA client & Chart.js rendering
│   ├── assets/               # Brand assets & UI iconography
│   └── index.html            # Single Page Application interface
├── setup.bat                 # Automated Windows environment installer
├── start.bat                 # One-click startup runner for backend and frontend
├── LICENSE                   # Source code licensing terms
└── README.md                 # Project dossier & technical documentation
```

---

## ⚖️ License

- **Source Code**: Licensed under the [MIT License](LICENSE).
- **Visual Assets (PNG Files)**: Copyright &copy; 2026 Pratik. All rights reserved. All PNG graphics and logos in `frontend/assets/` are protected proprietary creative works.
