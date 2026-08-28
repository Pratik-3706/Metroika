# Metroika — Legal Metrology Compliance Checker

> **SIH 2026 · SIH26034** — Software System to check compliance of Packaged Commodities under Legal Metrology (Packaged Commodities) Rules, 2011

AI-powered web application that scans product labels and images to automatically assess compliance with India's Legal Metrology rules.

## Features

- **Multi-Image Upload** — Upload front, back, side views of product labels
- **AI Vision Analysis** — Kimi K2.5 vision model extracts label text & declarations
- **Barcode/QR Scanning** — Automatic barcode detection via pyzbar
- **15 Compliance Checks** — Validated against Rules 6, 7, and 8
- **PDF Reports** — Color-coded compliance reports with evidence
- **Enforcement Dashboard** — Compliance stats, violation trends, charts
- **Product Repository** — Searchable history of all scanned products

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async), SQLite |
| AI Vision | Kimi K2.5 via OpenAI SDK (aicredits.in API) |
| Barcode | pyzbar (EAN-13, UPC-A, QR, Code128) |
| PDF | ReportLab |
| Frontend | Vanilla HTML/CSS/JS SPA |
| Charts | Chart.js |

## Setup

### 1. Clone & Enter Project
```bash
cd Metroika
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment (already created if you followed setup)
python -m venv venv

# Activate venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API Key
Edit `backend/.env` and set your API key:
```
AICREDITS_API_KEY=your_actual_api_key_here
```

### 4. Start Backend
```bash
cd backend
venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

### 5. Start Frontend
```bash
cd frontend
python -m http.server 3000
```

### 6. Open App
Navigate to `http://localhost:3000`

## API Documentation

Once the backend is running, visit `http://localhost:8000/docs` for interactive Swagger API docs.

## Compliance Rules Checked

| # | Rule | What's Validated |
|---|------|-----------------|
| 1 | Rule 6(1)(a) | Manufacturer/Packer/Importer name |
| 2 | Rule 6(1)(a) | Complete address |
| 3 | Rule 6(1)(b) | Generic name of commodity |
| 4 | Rule 6(1)(c) | Net quantity in SI units |
| 5 | Rule 6(1)(d) | Month & year of manufacture |
| 6 | Rule 6(1)(e) | MRP inclusive of all taxes |
| 7 | Rule 6(1)(f) | Consumer care details |
| 8 | Rule 6(1)(g) | Country of origin (imported) |
| 9 | Rule 6(1)(e) | MRP format validation |
| 10 | Rule 6(1)(d) | Date format validation |
| 11 | Rule 7 | Font size vs PDP area |
| 12 | Rule 8 | Principal Display Panel |
| 13 | Rule 6(3) | Language (English/Hindi) |
| 14 | Best Practice | Barcode/QR code presence |
| 15 | Rule 6(2) | Unit sale price |

## License

Built for Smart India Hackathon 2026.
