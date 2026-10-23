# ChronoLab Deployment & Production Operations Guide

This guide details how ChronoLab is configured for **high-availability production deployment** across major cloud platforms (Render, Railway, Docker, AWS/GCP).

---

## 🏗️ 1. Architecture Overview (12-Factor App)

ChronoLab follows the **Twelve-Factor App** principles for cloud-native deployment:

```
                      [ HTTPS Traffic (Internet) ]
                                   │
                                   ▼
                 [ Cloud Reverse Proxy / CDN (SSL Termination) ]
                                   │
                                   ▼
           [ Gunicorn WSGI Worker Cluster (3 Workers, Timeout: 120s) ]
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
         [ ChronoLab Flask Engine ]       [ /healthz Endpoint ]
                    │                             │
                    ▼                             ▼
       [ PostgreSQL 15 / SQLite ]      [ Container Healthcheck ]
```

---

## 🚀 2. Option A: 1-Click Free Cloud Deployment (Render.com)

Render provides a completely free tier with automated SSL certificates and Git-based deployment.

1. **Push your code to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "feat: production-ready ChronoLab v1.2"
   git remote add origin https://github.com/<your-username>/ChronoLab.git
   git push -u origin main
   ```

2. **Connect to Render**:
   - Log into [Render.com](https://render.com).
   - Click **New** $\rightarrow$ **Blueprint**.
   - Select your GitHub `ChronoLab` repository.
   - Render will automatically read [`render.yaml`](file:///C:/Users/VICTUS%20USER/OneDrive/Desktop/ChronoLab/render.yaml) and configure:
     - Runtime: `Python`
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `gunicorn wsgi:app --workers 3 --timeout 120`
     - Health Check Path: `/healthz`

3. **Your Live URL**:
   Your app will be live at `https://chronolab-intelligence.onrender.com` with a valid HTTPS certificate.

---

## 🐳 3. Option B: Docker Container Deployment

ChronoLab includes an enterprise **multi-stage Dockerfile** with a non-root system user (`chronouser`) to satisfy healthcare compliance audits.

### Local Docker Build & Run:
```bash
# Build the container
docker build -t chronolab:latest .

# Run the container
docker run -d -p 5000:5000 --name chronolab_prod chronolab:latest
```

### Full-Stack Docker Compose (Flask + PostgreSQL):
To run ChronoLab alongside a dedicated PostgreSQL 15 database:
```bash
docker compose up -d
```
The application will launch on `http://localhost:5000` with the database automatically initialized.

---

## 🛡️ 4. Production Security & Data Integrity Features

1. **`/healthz` Automated Probing Endpoint**:
   Provides an unauthenticated JSON health check endpoint (`{"status": "healthy"}`) used by cloud orchestrators (Render, AWS ALB, Kubernetes) to monitor container liveness.
2. **Strict File Upload Cap (16 MB)**:
   Configured in `config.py` using `MAX_CONTENT_LENGTH = 16 * 1024 * 1024` to prevent buffer overflow or DoS attacks via oversized documents.
3. **Session Cookie Hardening**:
   Cookies are tagged with `HttpOnly`, `SameSite=Lax`, and `Secure` (when running over HTTPS) to prevent XSS session hijacking.
4. **Non-Root Execution**:
   The Docker container runs under `USER chronouser`, preventing container breakout attacks.

---

## 🧪 5. Automated CI/CD Regression Testing

ChronoLab includes a **GitHub Actions workflow** (`.github/workflows/ci.yml`) that runs 7 automated unit and integration tests on every commit:

- `test_healthz_endpoint`: Verifies orchestrator probe status
- `test_dashboard_renders`: Verifies template rendering and data binding
- `test_pdf_export_pii_masked`: Validates ReportLab PDF stream generation
- `test_biomarker_alias_matching`: Verifies Jaccard token entity resolution
- `test_unit_conversion_math`: Tests molecular weight formulas
- `test_relative_range_position`: Tests statistical range normalization
- `test_derived_ratios_calculation`: Verifies cross-marker clinical ratio calculations

To run the test suite locally at any time:
```bash
pytest -v tests/
```
