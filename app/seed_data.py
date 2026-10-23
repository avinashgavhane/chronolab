"""
ChronoLab - Sample Data & Synthetic Diagnostic Generator
=========================================================
Populates realistic multi-year longitudinal medical data across multiple labs:
- Fasting Glucose & HbA1c demonstrating active pre-diabetic drift (+6.5 mg/dL/yr)
- Serum Creatinine & eGFR demonstrating renal stability
- Lipids demonstrating Statin intervention effect (Before vs. After)
- A synthetic prescription image for the confidence-gated fallback demo
"""

import os
from datetime import date, datetime, timedelta
from PIL import Image, ImageDraw, ImageFont

from app.models import db, Patient, CanonicalMarker, MarkerAlias, LabReport, TestResult, Medication, Prescription
from app.normalizer import (
    CANONICAL_CATALOG,
    compute_relative_range_position,
    calculate_annual_velocity,
    is_velocity_adverse
)


def seed_canonical_catalog():
    """Seeds the canonical medical dictionary into the database."""
    if CanonicalMarker.query.first():
        return  # Already seeded

    for code, meta in CANONICAL_CATALOG.items():
        marker = CanonicalMarker(
            code=code,
            name=meta["name"],
            panel=meta["panel"],
            canonical_unit=meta["canonical_unit"],
            default_min_range=meta.get("default_min"),
            default_max_range=meta.get("default_max"),
            is_higher_better=meta.get("is_higher_better", False)
        )
        db.session.add(marker)
        db.session.flush()

        for alias in meta["aliases"]:
            db.session.add(MarkerAlias(
                canonical_marker_id=marker.id,
                raw_alias_string=alias
            ))

    db.session.commit()


def create_sample_prescription_image(output_path: str):
    """Draws a synthetic doctor prescription note image for the snippet fallback demo."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img = Image.new("RGB", (650, 320), color="#FDFBF7")
    draw = ImageDraw.Draw(img)

    # Draw header banner
    draw.rectangle([10, 10, 640, 60], fill="#0284C7")
    draw.text((25, 20), "APOLLO CLINICAL HOSPITAL - Rx ENCOUNTER", fill="white")
    draw.text((25, 40), "Dr. Arvind Sharma, MD (Internal Medicine) | Reg: 74921", fill="#E0F2FE")

    # Draw simulated handwriting lines & prescription text
    draw.text((30, 80), "Patient: Rajesh Kumar | Age: 48 | Sex: M | Date: 12-Jan-2024", fill="#1E293B")
    draw.line([(20, 110), (630, 110)], fill="#CBD5E1", width=1)

    # Doctor cursive notes
    draw.text((40, 130), "Rx:", fill="#0F172A")
    draw.text((70, 140), "1. Tab. Metformin 500 mg - 1 tab OD after dinner (x 90 days)", fill="#1E3A8A")
    draw.text((70, 175), "2. Tab. Atorvastatin 10 mg - 1 tab HS (nightly)", fill="#1E3A8A")
    draw.text((70, 210), "Advise: 40 min brisk walk, cut sugar & refined carbs.", fill="#334155")
    draw.text((70, 240), "Review with repeat Fasting Glucose + HbA1c in 3 months.", fill="#DC2626")

    # Sign box
    draw.rectangle([450, 260, 620, 305], outline="#94A3B8")
    draw.text((465, 275), "[Dr. A. Sharma]", fill="#047857")

    img.save(output_path, "PNG")


from app.models import db, User, Patient, Doctor, DoctorPatientConsent, CanonicalMarker, MarkerAlias, LabReport, TestResult, Medication, Prescription

def seed_demo_patient(upload_folder: str) -> Patient:
    """Creates a complete realistic demo patient, doctor, and default admin user."""
    seed_canonical_catalog()

    # Seed Admin User if not present
    admin_user = User.query.filter_by(email="admin@chronolab.com").first()
    if not admin_user:
        admin_user = User(email="admin@chronolab.com", role="admin")
        admin_user.set_password("Admin@123")
        db.session.add(admin_user)
        db.session.commit()

    # Seed Doctor User & Profile if not present
    doc_user = User.query.filter_by(email="doctor@chronolab.com").first()
    if not doc_user:
        doc_user = User(email="doctor@chronolab.com", role="doctor")
        doc_user.set_password("Doctor@123")
        db.session.add(doc_user)
        db.session.flush()

        doctor = Doctor(
            user_id=doc_user.id,
            doctor_id="DOC-2026-401",
            full_name="Dr. Arvind Sharma, MD",
            specialty="Internal Medicine & Diabetology",
            registration_number="MCI-74921",
            hospital_affiliation="Apollo Clinical Hospital"
        )
        db.session.add(doctor)
        db.session.commit()

    patient = Patient.query.filter_by(chrono_id="CHRN-2026-8491").first()
    if patient:
        # Ensure consent exists
        doc = Doctor.query.filter_by(doctor_id="DOC-2026-401").first()
        if doc and not DoctorPatientConsent.query.filter_by(patient_id=patient.id, doctor_id=doc.id).first():
            db.session.add(DoctorPatientConsent(patient_id=patient.id, doctor_id=doc.id, status="ACTIVE"))
            db.session.commit()
        return patient

    # Seed Patient User Account
    patient_user = User.query.filter_by(email="patient@chronolab.com").first()
    if not patient_user:
        patient_user = User(email="patient@chronolab.com", role="patient")
        patient_user.set_password("Patient@123")
        db.session.add(patient_user)
        db.session.flush()

    patient = Patient(
        user_id=patient_user.id,
        chrono_id="CHRN-2026-8491",
        full_name="Rajesh Kumar",
        date_of_birth=date(1978, 5, 14),
        biological_sex="MALE",
        blood_group="B+"
    )
    db.session.add(patient)
    db.session.flush()

    # Active Medication
    db.session.add(Medication(
        patient_id=patient.id,
        drug_name="Metformin",
        dosage="500mg",
        frequency="Once daily - Post Dinner",
        start_date=date(2024, 1, 15),
        notes="Started following upward fasting blood sugar trend."
    ))
    db.session.add(Medication(
        patient_id=patient.id,
        drug_name="Atorvastatin",
        dosage="10mg",
        frequency="Once daily - Bedtime",
        start_date=date(2024, 6, 10),
        notes="Targeting elevated LDL."
    ))

    # Synthetic Prescription with Snippet Fallback
    snippet_dir = os.path.join(upload_folder, "snippets")
    sample_rx_img = os.path.join(upload_folder, "sample_rx.png")
    create_sample_prescription_image(sample_rx_img)

    # Create cropped snippet
    os.makedirs(snippet_dir, exist_ok=True)
    crop_dest = os.path.join(snippet_dir, "demo_rx_crop.png")
    with Image.open(sample_rx_img) as rx:
        w, h = rx.size
        cropped = rx.crop((20, 115, w-20, 255))
        cropped.save(crop_dest, "PNG")

    db.session.add(Prescription(
        patient_id=patient.id,
        encounter_date=date(2024, 1, 12),
        doctor_name="Dr. Arvind Sharma, MD",
        clinic_or_hospital="Apollo Clinical Hospital",
        ocr_confidence_score=78.4,
        structured_notes="[Low-Confidence OCR: Fallback to authentic handwriting artifact]",
        is_handwriting_fallback=True,
        snippet_image_path="uploads/snippets/demo_rx_crop.png"
    ))

    # 4 Multi-Year Lab Reports Across Different Diagnostic Chains
    # Lab 1: Quest Diagnostics (3 years ago)
    # Lab 2: Dr Lal PathLabs (2 years ago)
    # Lab 3: Metropolis Healthcare (1 year ago)
    # Lab 4: Apollo Diagnostics (Recent)
    reports_data = [
        {
            "lab": "Quest Diagnostics",
            "date": date(2023, 2, 10),
            "results": {
                "FASTING_GLUCOSE": (78.0, "mg/dL", 70.0, 99.0),
                "HBA1C": (5.3, "%", 4.0, 5.6),
                "TOTAL_CHOLESTEROL": (195.0, "mg/dL", 125.0, 200.0),
                "HDL_CHOLESTEROL": (46.0, "mg/dL", 40.0, 60.0),
                "LDL_CHOLESTEROL": (118.0, "mg/dL", 0.0, 100.0),
                "TRIGLYCERIDES": (155.0, "mg/dL", 0.0, 150.0),
                "SERUM_CREATININE": (0.90, "mg/dL", 0.7, 1.2),
                "EGFR": (98.0, "mL/min/1.73m2", 90.0, 120.0),
                "ALT_SGPT": (28.0, "U/L", 7.0, 45.0),
                "AST_SGOT": (24.0, "U/L", 8.0, 40.0),
                "VITAMIN_D": (22.5, "ng/mL", 30.0, 100.0)
            }
        },
        {
            "lab": "Dr Lal PathLabs",
            "date": date(2024, 1, 8),
            "results": {
                "FASTING_GLUCOSE": (86.0, "mg/dL", 74.0, 100.0),  # Higher lab min
                "HBA1C": (5.6, "%", 4.0, 5.6),
                "TOTAL_CHOLESTEROL": (212.0, "mg/dL", 125.0, 200.0),
                "HDL_CHOLESTEROL": (42.0, "mg/dL", 40.0, 60.0),
                "LDL_CHOLESTEROL": (134.0, "mg/dL", 0.0, 100.0),
                "TRIGLYCERIDES": (180.0, "mg/dL", 0.0, 150.0),
                "SERUM_CREATININE": (0.94, "mg/dL", 0.7, 1.2),
                "EGFR": (95.0, "mL/min/1.73m2", 90.0, 120.0),
                "ALT_SGPT": (32.0, "U/L", 7.0, 45.0),
                "AST_SGOT": (26.0, "U/L", 8.0, 40.0),
                "VITAMIN_D": (62.0, "nmol/L", 75.0, 250.0)      # Different Unit! (62 nmol/L = 24.8 ng/mL)
            }
        },
        {
            "lab": "Metropolis Healthcare",
            "date": date(2024, 9, 20),
            "results": {
                "FASTING_GLUCOSE": (93.0, "mg/dL", 70.0, 99.0),
                "HBA1C": (5.9, "%", 4.0, 5.6),                  # Drifting into pre-diabetes
                "TOTAL_CHOLESTEROL": (175.0, "mg/dL", 125.0, 200.0), # Statin effect!
                "HDL_CHOLESTEROL": (44.0, "mg/dL", 40.0, 60.0),
                "LDL_CHOLESTEROL": (98.0, "mg/dL", 0.0, 100.0),      # Dropped from 134 to 98
                "TRIGLYCERIDES": (165.0, "mg/dL", 0.0, 150.0),
                "SERUM_CREATININE": (0.98, "mg/dL", 0.7, 1.2),
                "EGFR": (92.0, "mL/min/1.73m2", 90.0, 120.0),
                "ALT_SGPT": (38.0, "U/L", 7.0, 45.0),
                "AST_SGOT": (30.0, "U/L", 8.0, 40.0),
                "VITAMIN_D": (31.0, "ng/mL", 30.0, 100.0)
            }
        },
        {
            "lab": "Apollo Diagnostics",
            "date": date(2025, 4, 15),
            "results": {
                "FASTING_GLUCOSE": (99.0, "mg/dL", 70.0, 99.0),   # 99 mg/dL - right on border! (+7 mg/dL/yr drift!)
                "HBA1C": (6.2, "%", 4.0, 5.6),                   # Pre-diabetes confirmed
                "TOTAL_CHOLESTEROL": (168.0, "mg/dL", 125.0, 200.0),
                "HDL_CHOLESTEROL": (45.0, "mg/dL", 40.0, 60.0),
                "LDL_CHOLESTEROL": (92.0, "mg/dL", 0.0, 100.0),
                "TRIGLYCERIDES": (158.0, "mg/dL", 0.0, 150.0),
                "SERUM_CREATININE": (0.99, "mg/dL", 0.7, 1.2),
                "EGFR": (91.0, "mL/min/1.73m2", 90.0, 120.0),
                "ALT_SGPT": (39.0, "U/L", 7.0, 45.0),
                "AST_SGOT": (31.0, "U/L", 8.0, 40.0),
                "VITAMIN_D": (34.0, "ng/mL", 30.0, 100.0)
            }
        }
    ]

    for rep_data in reports_data:
        report = LabReport(
            patient_id=patient.id,
            lab_name=rep_data["lab"],
            test_date=rep_data["date"],
            original_filename=f"{rep_data['lab'].lower().replace(' ', '_')}_{rep_data['date'].strftime('%Y%m%d')}.pdf"
        )
        db.session.add(report)
        db.session.flush()

        for code, (val, unit, min_r, max_r) in rep_data["results"].items():
            marker = CanonicalMarker.query.filter_by(code=code).first()
            if not marker:
                continue

            # Unit normalization
            norm_val = val
            norm_unit = unit
            if code == "VITAMIN_D" and "nmol" in unit:
                norm_val = round(val * 0.40064, 2)
                norm_unit = "ng/mL"

            rrp = compute_relative_range_position(norm_val, min_r, max_r)

            # Check previous test for velocity calculation
            prev_result = (
                TestResult.query
                .join(LabReport)
                .filter(
                    TestResult.patient_id == patient.id,
                    TestResult.canonical_marker_id == marker.id,
                    LabReport.test_date < rep_data["date"]
                )
                .order_by(LabReport.test_date.desc())
                .first()
            )

            velocity = None
            is_adv = False
            if prev_result:
                velocity = calculate_annual_velocity(norm_val, rep_data["date"], prev_result.normalized_value, prev_result.report.test_date)
                is_adv = is_velocity_adverse(code, velocity)

            db.session.add(TestResult(
                lab_report_id=report.id,
                patient_id=patient.id,
                canonical_marker_id=marker.id,
                raw_marker_name=marker.name,
                raw_value=val,
                raw_unit=unit,
                lab_min_range=min_r,
                lab_max_range=max_r,
                normalized_value=norm_val,
                normalized_unit=norm_unit,
                relative_range_position=rrp,
                velocity_delta_per_year=velocity,
                is_adverse_drift=is_adv
            ))

    doc = Doctor.query.filter_by(doctor_id="DOC-2026-401").first()
    if doc and not DoctorPatientConsent.query.filter_by(patient_id=patient.id, doctor_id=doc.id).first():
        db.session.add(DoctorPatientConsent(patient_id=patient.id, doctor_id=doc.id, status="ACTIVE"))

    db.session.commit()
    return patient
