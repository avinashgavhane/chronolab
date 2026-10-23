# ChronoLab: Longitudinal Multi-Lab Diagnostic Intelligence & Clinical Trajectory Engine

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask%203.1-black.svg)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20%2F%20SQLAlchemy-green.svg)](https://www.sqlalchemy.org/)
[![ReportLab](https://img.shields.io/badge/PDF_Engine-ReportLab-red.svg)](https://www.reportlab.com/)

ChronoLab is an architectural solution to **The Static Snapshot Trap** in healthcare diagnostics. Over 5 to 10 years, patients accumulate blood test reports across multiple independent diagnostic labs (Quest, Labcorp, Dr Lal PathLabs, Metropolis). Each provider utilizes conflicting nomenclature, divergent measurement units, and varying reference intervals.

ChronoLab normalizes multi-lab test time-series, computes annual biomarker drift velocity ($\Delta V / \Delta t$), and outputs a 1-page printable Physician Brief with PII de-identification to optimize 7-minute doctor consultations.

---

## 🚀 Key Features

1. **Deterministic Unit Normalization**: Automatically converts mismatched lab units (e.g., Vitamin D $nmol/L \leftrightarrow ng/mL$, Glucose $mmol/L \leftrightarrow mg/dL$, Creatinine $\mu mol/L \leftrightarrow mg/dL$) using exact molecular weight formulas.
2. **Relative Range Position ($RRP\%$)**: Standardizes values across conflicting laboratory reference intervals:
   $$RRP = \frac{\text{Observed Value} - \text{Range Min}}{\text{Range Max} - \text{Range Min}} \times 100\%$$
3. **Longitudinal Velocity Engine ($dV/dt$)**: Computes annual drift rates and flags sub-clinical deterioration before numbers breach lab "abnormal" boundaries (e.g., detecting $+6.7\text{ mg/dL/yr}$ pre-diabetic drift).
4. **Clinical Intervention Overlay**: Plots vertical timeline markers for medications (e.g. Statins, Metformin) to visualize Before vs. After efficacy curves.
5. **Derived Hidden Clinical Ratios**: Calculates cross-analyte ratios not computed by standard labs:
   - **Triglyceride / HDL Ratio**: Atherogenic dyslipidemia and insulin resistance predictor ($>3.5$ High Risk).
   - **De Ritis Ratio (AST / ALT)**: Distinguishes fatty liver patterns from acute hepatic injury.
   - **BUN / Creatinine Ratio**: Differentiates prerenal azotemia/dehydration from intrinsic renal decline.
6. **Zero-Hallucination Prescription Fallback**: High-confidence text extraction ($\ge 95\%$) vs. automatic image snippet cropping for ambiguous handwriting.
7. **1-Page Printable Physician Brief**: Executive summary PDF featuring side-by-side matrices, trajectory flags, and 1-click **PII De-identification (HIPAA Safe Harbor / DPDP)**.
8. **Intent-Driven Triage Flow**: 1-click login triage directing patients to Doctor Prep, Medication Checks, or Silent Drift Audits.

---

## 🛠️ Tech Stack & Architecture

- **Backend / Web Controller**: Python, Flask, Jinja2
- **Data Persistence**: SQLite / PostgreSQL via Flask-SQLAlchemy ORM
- **Tabular PDF Extraction**: PyMuPDF (`fitz`), `pdfplumber`, Regex Token State Machines
- **Ontology & String Matching**: Canonical Medical Catalog, `RapidFuzz` / Jaccard token similarity
- **Artifact Snippet Cropper**: Pillow (`PIL`)
- **PDF Generation**: ReportLab Platypus Engine
- **Frontend / Data Visualization**: HTML5, Tailwind CSS, Chart.js

---

## 📂 Project Directory Structure

```text
ChronoLab/
├── app/
│   ├── __init__.py           # Flask factory, route controllers, Chart.js API
│   ├── models.py             # 7 relational SQLAlchemy tables
│   ├── normalizer.py         # Medical catalog, unit math, RRP %, derived ratios
│   ├── parser.py             # PDF tabular extraction & handwriting snippet cropper
│   ├── pdf_generator.py      # ReportLab 1-page printable Physician Brief generator
│   ├── seed_data.py          # Realistic multi-year patient test data generator
│   └── templates/
│       ├── base.html         # Tailwind navigation, ChronoID badge, flash alerts
│       ├── dashboard.html    # Triage cards, velocity alerts, Chart.js graphs
│       └── upload.html       # Drag-and-drop PDF & prescription image uploaders
├── uploads/
│   ├── reports/              # Uploaded lab report PDFs
│   └── snippets/             # Cropped handwriting fallback images
├── run.py                    # Server launch entrypoint
└── README.md
```

---

## ⚡ Quickstart & Running Locally

1. **Clone or Navigate to the Directory**:
   ```bash
   cd "C:\Users\VICTUS USER\OneDrive\Desktop\ChronoLab"
   ```

2. **Install Dependencies**:
   ```bash
   python -m pip install flask flask-sqlalchemy reportlab pdfplumber rapidfuzz pymupdf pillow
   ```

3. **Start the Development Server**:
   ```bash
   python run.py
   ```

4. **Access the Application**:
   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.
   - Pre-loaded with **Rajesh Kumar (`CHRN-2026-8491`)** across 4 multi-year lab reports (Quest, Dr Lal, Metropolis, Apollo).
   - Test the **1-Page PDF Brief** with the PII Masking toggle enabled.
   - Observe the **Before vs. After Statin intervention curve** on the Lipid panel.
