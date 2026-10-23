# ChronoLab System Architecture & Engineering Specifications

This document provides a comprehensive technical overview of **ChronoLab**'s system architecture, data ingestion pipelines, entity resolution mechanisms, mathematical normalization models, database schemas, and cloud deployment topology.

---

## 1. High-Level System Architecture

ChronoLab is built on a **modular 5-tier architecture** following 12-factor cloud-native application standards:

```mermaid
graph TD
    Client["Client Devices<br/>(Mobile Browser / Desktop PWA)"]

    subgraph Edge_Reverse_Proxy["Edge & Reverse Proxy Layer"]
        CDN["Cloud CDN / Cloudflare<br/>(TLS 1.3 Termination)"]
        WSGI["Gunicorn WSGI Server<br/>(3 Concurrency Workers)"]
    end

    subgraph App_Core["Application Controller Layer (Flask 3.1)"]
        AuthMiddleware["Session Auth & Role Gatekeeper<br/>(Admin vs. Patient)"]
        HealthEndpoint["/healthz Liveness Probe"]
        Router["Application Dispatcher & API Routes"]
    end

    subgraph Ingestion_Pipelines["Processing & Extraction Pipeline"]
        PDFParser["PyMuPDF / pdfminer Text Engine"]
        ImageOCR["Image Document Normalizer<br/>(Camera / Paper Scans)"]
        SnippetCropper["Pillow (PIL) Bounding-Box Cropper<br/>(Confidence-Gated Handwriting Fallback)"]
    end

    subgraph Intelligence_Layer["Clinical Intelligence & Analytics Engine"]
        FuzzyMatcher["Jaccard & RapidFuzz<br/>Entity Resolution Engine"]
        UnitConverter["Molecular Weight Conversion Engine"]
        RRPCalculator["Relative Range Position (RRP %) Calculator"]
        VelocityEngine["Longitudinal Drift Engine (dV/dt)"]
        RatioSynthesizer["Cross-Marker Ratio Synthesizer<br/>(TG/HDL, AST/ALT, BUN/Cr)"]
    end

    subgraph Output_Engine["Document Generation & Presentation"]
        ChartService["Chart.js Dynamic Dataset Formatter"]
        PDFCompiler["ReportLab Platypus Engine<br/>(1-Page Physician Brief)"]
        PIIMasker["De-Identification Engine<br/>(HIPAA Safe Harbor / DPDP)"]
    end

    subgraph Persistence_Layer["Data Persistence Layer"]
        ORM["SQLAlchemy ORM (Connection Pool)"]
        Database[("PostgreSQL 15 / SQLite DB<br/>8 Relational Tables")]
        DiskStorage[("Isolated Storage Vault<br/>/uploads/reports & /uploads/snippets")]
    end

    Client -->|HTTPS / REST| CDN
    CDN --> WSGI
    WSGI --> AuthMiddleware
    AuthMiddleware --> Router
    Router --> HealthEndpoint
    Router --> PDFParser
    Router --> ImageOCR

    PDFParser --> FuzzyMatcher
    ImageOCR --> FuzzyMatcher
    ImageOCR --> SnippetCropper

    FuzzyMatcher --> UnitConverter
    UnitConverter --> RRPCalculator
    RRPCalculator --> VelocityEngine
    VelocityEngine --> RatioSynthesizer

    RatioSynthesizer --> ORM
    SnippetCropper --> DiskStorage
    ORM --> Database

    Router --> ChartService
    Router --> PDFCompiler
    PDFCompiler --> PIIMasker
    PIIMasker --> Client
    ChartService --> Client
```

---

## 2. Ingestion & Normalization Pipeline Flow

The diagnostic ingestion pipeline standardizes unstructured medical inputs through sequential transformation phases:

```mermaid
sequenceDiagram
    autonumber
    actor User as Patient / Clinician
    participant App as Flask Controller
    participant Extractor as Extraction Engine (PyMuPDF)
    participant Resolver as Entity Resolution (Jaccard)
    participant Normalizer as Molecular Unit Normalizer
    participant Velocity as Velocity Engine (dV/dt)
    participant DB as Relational Store (SQLAlchemy)
    participant PDF as ReportLab PDF Engine

    User->>App: Upload Lab Report (PDF / Camera Photo)
    App->>Extractor: Ingest Raw Document Bytes
    Extractor->>Extractor: Segment Bounding Coordinates & Tabular Tokens
    Extractor-->>App: Extracted Raw Records: (Date, Name, Value, Unit, Range)

    loop For Each Extracted Biomarker Row
        App->>Resolver: Resolve Raw String (e.g., 'fbs blood sugar')
        Resolver-->>App: Canonical Biomarker Code (e.g., 'FASTING_GLUCOSE')
        
        App->>Normalizer: Normalize Unit (e.g., 5.5 mmol/L Glucose)
        Normalizer-->>App: Normalized Value (99.09 mg/dL) + Standard Unit
        
        App->>Normalizer: Calculate Relative Range Position (RRP %)
        Normalizer-->>App: RRP Score (e.g., 96.6% of reference band)
        
        App->>Velocity: Query Chronological Prior Test from DB
        Velocity-->>App: Annual Velocity Delta: dV/dt (+6.7 mg/dL/yr -> Adverse Drift: True)
        
        App->>DB: Persist Raw & Normalized Results (Audit-Safe)
    end

    User->>App: Request 1-Page Physician Consultation Brief
    App->>PDF: Compile Matrix, Intervention Markers, & Ratios
    App->>PDF: Apply 1-Click PII De-Identification Mask
    PDF-->>User: Download Standardized 1-Page PDF Brief
```

---

## 3. Mathematical & Algorithmic Models

ChronoLab avoids non-deterministic generative models for clinical calculations, relying entirely on auditable mathematical and statistical standards:

### 3.1. Molecular Weight Unit Conversion
International diagnostic labs report identical analytes in disparate units. ChronoLab computes conversions using specific molecular masses ($M_r$):

* **Fasting Blood Glucose ($M_r = 180.16\text{ g/mol}$):**
  $$\text{Value}_{\text{mg/dL}} = \text{Value}_{\text{mmol/L}} \times 18.016$$

* **Total, HDL, & LDL Cholesterol ($M_r = 386.65\text{ g/mol}$):**
  $$\text{Value}_{\text{mg/dL}} = \text{Value}_{\text{mmol/L}} \times 38.67$$

* **Serum Triglycerides ($M_r \approx 885.7\text{ g/mol}$):**
  $$\text{Value}_{\text{mg/dL}} = \text{Value}_{\text{mmol/L}} \times 88.57$$

* **25-Hydroxy Vitamin D:**
  $$\text{Value}_{\text{ng/mL}} = \text{Value}_{\text{nmol/L}} \times 0.40064$$

* **Serum Creatinine:**
  $$\text{Value}_{\text{mg/dL}} = \frac{\text{Value}_{\mu\text{mol/L}}}{88.4}$$

---

### 3.2. Relative Range Position ($RRP\%$) Normalization
Different equipment manufacturers (Roche, Abbott, Siemens) utilize conflicting biological reference intervals. Raw values alone cause false alarms when patients switch healthcare providers. ChronoLab normalizes readings relative to the reporting lab's reference band:

$$RRP = \left( \frac{\text{Observed Value} - \text{Reference Min}}{\text{Reference Max} - \text{Reference Min}} \right) \times 100\%$$

* **$RRP = 50\%$**: Exactly centered in optimal range.
* **$0\% \le RRP \le 100\%$**: Within normal clinical limits.
* **$RRP > 100\%$**: Clinically elevated above reporting lab's threshold.
* **$RRP < 0\%$**: Clinically depressed below reporting lab's threshold.

---

### 3.3. Annual Biomarker Trajectory Velocity ($dV/dt$)
To expose sub-clinical disease drift before values exceed standard thresholds, ChronoLab evaluates longitudinal rate-of-change:

$$\text{Velocity} = \left( \frac{\text{Value}_{\text{latest}} - \text{Value}_{\text{prior}}}{\Delta t_{\text{days}}} \right) \times 365.25$$

* **Adverse Drift Trigger Examples:**
  - $\Delta \text{Fasting Glucose} \ge +4.0\text{ mg/dL/year} \longrightarrow \textbf{Pre-Diabetic Drift Alert}$
  - $\Delta \text{HbA1c} \ge +0.20\%\text{/year} \longrightarrow \textbf{Metabolic Deterioration Alert}$
  - $\Delta \text{eGFR} \le -3.0\text{ mL/min/1.73m}^2\text{/year} \longrightarrow \textbf{Renal Decline Alert}$

---

### 3.4. Derived Cross-Marker Physiological Ratios
1. **Triglyceride-to-HDL Ratio:**
   $$\text{Ratio} = \frac{\text{Triglycerides}}{\text{HDL}}$$
   - $\text{Ratio} < 2.0$: Optimal
   - $2.0 \le \text{Ratio} \le 3.5$: Borderline
   - $\text{Ratio} > 3.5$: High Risk (Predictor of atherogenic dyslipidemia and insulin resistance)

2. **De Ritis Ratio (AST / ALT):**
   $$\text{Ratio} = \frac{\text{AST (SGOT)}}{\text{ALT (SGPT)}}$$
   - Distinguishes non-alcoholic fatty liver disease (NAFLD, $<1.0$) from alcoholic or acute toxic hepatic injury ($>2.0$).

3. **BUN-to-Creatinine Ratio:**
   $$\text{Ratio} = \frac{\text{Blood Urea Nitrogen}}{\text{Serum Creatinine}}$$
   - Differentiates prerenal azotemia / dehydration ($>20:1$) from intrinsic renal parenchymal decline ($10:1 \text{--} 20:1$).

---

## 4. Entity-Relationship Data Model (ERD)

The database schema is fully normalized into 8 relational tables enforcing foreign key integrity, cascade deletions, and index optimization for time-series lookups:

```mermaid
erDiagram
    USERS ||--o| PATIENTS : "1-to-1 owns"
    PATIENTS ||--o{ LAB_REPORTS : "1-to-Many uploads"
    PATIENTS ||--o{ TEST_RESULTS : "1-to-Many longitudinal records"
    PATIENTS ||--o{ MEDICATIONS : "1-to-Many interventions"
    PATIENTS ||--o{ PRESCRIPTIONS : "1-to-Many encounters"
    
    LAB_REPORTS ||--o{ TEST_RESULTS : "1-to-Many contains"
    CANONICAL_MARKERS ||--o{ TEST_RESULTS : "1-to-Many categorizes"
    CANONICAL_MARKERS ||--o{ MARKER_ALIASES : "1-to-Many resolves"

    USERS {
        int id PK
        string email UK
        string password_hash
        string role
        boolean is_active
        datetime created_at
    }

    PATIENTS {
        int id PK
        int user_id FK
        string chrono_id UK
        string full_name
        date date_of_birth
        string biological_sex
        string blood_group
        datetime created_at
    }

    CANONICAL_MARKERS {
        int id PK
        string code UK
        string name
        string panel
        string canonical_unit
        float default_min_range
        float default_max_range
        boolean is_higher_better
    }

    MARKER_ALIASES {
        int id PK
        int canonical_marker_id FK
        string raw_alias_string UK
    }

    LAB_REPORTS {
        int id PK
        int patient_id FK
        string lab_name
        date test_date
        string original_filename
        datetime uploaded_at
    }

    TEST_RESULTS {
        int id PK
        int lab_report_id FK
        int patient_id FK
        int canonical_marker_id FK
        string raw_marker_name
        float raw_value
        string raw_unit
        float lab_min_range
        float lab_max_range
        float normalized_value
        string normalized_unit
        float relative_range_position
        float velocity_delta_per_year
        boolean is_adverse_drift
        datetime created_at
    }

    MEDICATIONS {
        int id PK
        int patient_id FK
        string drug_name
        string dosage
        string frequency
        date start_date
        date end_date
        text notes
    }

    PRESCRIPTIONS {
        int id PK
        int patient_id FK
        date encounter_date
        string doctor_name
        string clinic_or_hospital
        float ocr_confidence_score
        text structured_notes
        boolean is_handwriting_fallback
        string snippet_image_path
        datetime created_at
    }
```

---

## 5. Security, Privacy, & Healthcare Compliance

| Compliance Requirement | Implementation in ChronoLab |
| :--- | :--- |
| **HIPAA Safe Harbor (§164.514)** | 1-Click PII de-identification replaces Name, Contact, and Geographic data with a pseudonymous `ChronoID` (`CHRN-XXXX-XXXX`) on all external PDF exports. |
| **India DPDP Act 2023** | Strictly avoids raw 12-digit Aadhaar storage. Implements pseudonymous tokenization modeled after the National Health Authority (NHA) ABHA framework. |
| **Zero-Hallucination Fallback** | Enforces a $\ge 95\%$ OCR confidence gate for prescriptions. Ambiguous handwriting is never transcribed; it is cropped as an authentic visual snippet to eliminate medical dosage errors. |
| **OWASP Container Hardening** | Multi-stage Docker container runs under an unprivileged non-root system user (`USER chronouser`, UID 1000). |
| **Denial of Service Prevention** | Enforces `MAX_CONTENT_LENGTH = 16MB` upload limits and coordinate boundary timeouts on PDF parsing. |
| **Session Protection** | Session cookies utilize `HttpOnly`, `SameSite=Lax`, and automated `Secure=True` in production environments. |

---

## 6. Cloud Deployment & Container Topology

```mermaid
graph LR
    subgraph Production_Container["Docker Container (Linux Alpine / Debian Slim)"]
        Gunicorn["Gunicorn WSGI Master<br/>(3 Concurrency Workers)"]
        FlaskWorker1["Worker 1 (Flask)"]
        FlaskWorker2["Worker 2 (Flask)"]
        FlaskWorker3["Worker 3 (Flask)"]
        HealthProbe["Liveness Probe: /healthz"]
    end

    subgraph Managed_Cloud_Services["Managed Cloud Services (Render / AWS)"]
        LB["Cloud Load Balancer (Auto-TLS)"]
        PostgresService[("Managed PostgreSQL 15 Database")]
        StorageMount[("Encrypted Persistent Volume<br/>/app/uploads")]
    end

    InternetTraffic((Public Web Traffic)) --> LB
    LB -->|Port 5000| Gunicorn
    Gunicorn --> FlaskWorker1
    Gunicorn --> FlaskWorker2
    Gunicorn --> FlaskWorker3
    LB --> HealthProbe

    FlaskWorker1 --> PostgresService
    FlaskWorker2 --> PostgresService
    FlaskWorker3 --> PostgresService

    FlaskWorker1 --> StorageMount
    FlaskWorker2 --> StorageMount
    FlaskWorker3 --> StorageMount
```

---

## 7. CI/CD Pipeline & Quality Assurance

ChronoLab enforces quality through an automated **GitHub Actions CI/CD pipeline** (`.github/workflows/ci.yml`) triggering on all PRs and pushes to `main`:

```
[ Git Push / PR ] 
       │
       ▼
1. Dependency Resolution (Python 3.11/3.14 Cache)
       │
       ▼
2. Automated Unit & Integration Suite (`pytest -v tests/`)
   ├── test_healthz_endpoint              -> Liveness probe returns 200 OK
   ├── test_dashboard_renders             -> View bindings & auth context
   ├── test_pdf_export_pii_masked         -> ReportLab stream generation & masking
   ├── test_biomarker_alias_matching      -> Token Jaccard entity resolution
   ├── test_unit_conversion_math          -> Molecular weight conversion formulas
   ├── test_relative_range_position       -> Statistical RRP % validation
   └── test_derived_ratios_calculation    -> TG/HDL, AST/ALT risk triggers
       │
       ▼
3. Zero-Failure Merge Gate -> Automated Deployment (Render / Docker Registry)
```
