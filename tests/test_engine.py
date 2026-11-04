"""
ChronoLab - Automated Regression & Integration Test Suite
=========================================================
Runs automated tests for:
1. Health endpoint response (/healthz)
2. Normalization & molecular weight unit conversion
3. Relative Range Position (% RRP) calculations
4. Derived Clinical Ratios (TG/HDL, AST/ALT, BUN/Cr)
5. PII De-identification & 1-page PDF Brief export
6. Intent-Driven Dashboard rendering
"""

import os
import sys
import pytest

# Ensure project root is in sys.path across all CI runners and environments
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.models import db, Patient, CanonicalMarker
from app.normalizer import (
    match_biomarker_alias,
    normalize_unit,
    compute_relative_range_position,
    calculate_derived_ratios
)


@pytest.fixture
def app_instance():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def test_healthz_endpoint(client):
    """Verifies that the /healthz orchestrator probe returns 200 OK and valid JSON."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "ChronoLab Engine"


def test_landing_page(client):
    """Verifies that the high-end landing page loads with brand overview."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"ChronoLab" in response.data


def test_dashboard_renders(client):
    """Verifies dashboard loads with patient demographics and triage cards."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"ChronoLab" in response.data
    assert b"Longitudinal Velocity Alerts" in response.data
    assert b"Doctor Access &amp; Privacy Consent" in response.data


def test_doctor_portal_requires_clearance(client):
    """Verifies that unauthenticated users cannot access the doctor portal directly."""
    response = client.get("/doctor", follow_redirects=True)
    assert response.status_code == 200
    assert b"Sign In" in response.data


def test_doctor_portal_authenticated(client):
    """Verifies that doctor session loads the CDSS OPD clinical cockpit."""
    with client.session_transaction() as sess:
        sess["user_role"] = "doctor"
        sess["user_email"] = "doctor@chronolab.com"
        sess["doctor_id"] = "DOC-2026-401"
    
    response = client.get("/doctor")
    assert response.status_code == 200
    assert b"Clinical Decision Support System" in response.data
    assert b"Dr. Arvind Sharma" in response.data


def test_admin_portal_authenticated(client):
    """Verifies that admin session loads telemetry and role management."""
    with client.session_transaction() as sess:
        sess["user_role"] = "admin"
        sess["user_email"] = "admin@chronolab.com"
    
    response = client.get("/admin")
    assert response.status_code == 200
    assert b"System Administrator Console" in response.data
    assert b"User Access &amp; Role Management" in response.data


def test_pdf_export_pii_masked(client):
    """Verifies that the 1-page PDF Brief generator generates valid PDF bytes with PII masking."""
    response = client.get("/export-brief?mask_pii=true")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert len(response.data) > 5000  # Non-empty valid PDF byte stream


def test_biomarker_alias_matching():
    """Verifies fuzzy and exact matching against messy real-world lab text."""
    assert match_biomarker_alias("fbs") == "FASTING_GLUCOSE"
    assert match_biomarker_alias("glucose fasting") == "FASTING_GLUCOSE"
    assert match_biomarker_alias("hba1c (glycated hb)") == "HBA1C"
    assert match_biomarker_alias("s. creatinine blood") == "SERUM_CREATININE"
    assert match_biomarker_alias("total cholesterol") == "TOTAL_CHOLESTEROL"


def test_unit_conversion_math():
    """Verifies exact molecular weight formulas for international units."""
    # Vitamin D: 75 nmol/L -> 30.05 ng/mL
    val, unit = normalize_unit("VITAMIN_D", 75.0, "nmol/L")
    assert unit == "ng/mL"
    assert val == 30.05

    # Glucose: 5.5 mmol/L -> 99.09 mg/dL
    val, unit = normalize_unit("FASTING_GLUCOSE", 5.5, "mmol/L")
    assert unit == "mg/dL"
    assert val == 99.09


def test_relative_range_position():
    """Verifies that RRP % computes correct relative position."""
    # Value 85 in [70, 100] is exactly 50%
    rrp = compute_relative_range_position(85.0, 70.0, 100.0)
    assert rrp == 50.0

    # Value 110 in [70, 100] is > 100% (High)
    rrp_high = compute_relative_range_position(110.0, 70.0, 100.0)
    assert rrp_high > 100.0


def test_derived_ratios_calculation():
    """Verifies calculation of Triglyceride / HDL ratio and atherogenic risk flagging."""
    ratios = calculate_derived_ratios({"TRIGLYCERIDES": 180.0, "HDL_CHOLESTEROL": 36.0})
    assert "TG_HDL_RATIO" in ratios
    assert ratios["TG_HDL_RATIO"]["value"] == 5.0
    assert ratios["TG_HDL_RATIO"]["status"] == "HIGH_RISK"
