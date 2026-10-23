"""
ChronoLab - Database Models
===========================
Defines the relational schema using SQLAlchemy ORM for:
1. Patients (with unique ChronoID & PII isolation)
2. Canonical Biomarkers (standard clinical definitions)
3. Marker Aliases (mapping messy lab text to canonical markers)
4. Lab Reports (uploaded metadata)
5. Test Results (raw + normalized values, RRP %, annual velocity)
6. Medications (interventions for timeline overlay)
7. Prescriptions (confidence-gated notes & handwriting snippets)
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="patient")  # 'patient', 'doctor', or 'admin'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 1-to-1 linkage with patient profile (if patient)
    patient = db.relationship("Patient", backref="user", uselist=False, cascade="all, delete-orphan")
    # 1-to-1 linkage with doctor profile (if doctor)
    doctor = db.relationship("Doctor", backref="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    doctor_id = db.Column(db.String(30), unique=True, nullable=False, index=True)  # e.g., 'DOC-2026-401'
    full_name = db.Column(db.String(100), nullable=False)
    specialty = db.Column(db.String(100), default="Internal Medicine / General Physician")
    registration_number = db.Column(db.String(50), default="MCI-74921")
    hospital_affiliation = db.Column(db.String(120), default="Apollo Clinical Hospital")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Consents granted to this doctor
    consents = db.relationship("DoctorPatientConsent", backref="doctor", cascade="all, delete-orphan", lazy="dynamic")


class DoctorPatientConsent(db.Model):
    __tablename__ = "doctor_patient_consents"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    status = db.Column(db.String(20), default="ACTIVE")  # 'ACTIVE', 'REVOKED'
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True)


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    chrono_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    biological_sex = db.Column(db.String(10), nullable=False)  # 'MALE', 'FEMALE', 'OTHER'
    blood_group = db.Column(db.String(5), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    lab_reports = db.relationship("LabReport", backref="patient", cascade="all, delete-orphan", lazy="dynamic")
    test_results = db.relationship("TestResult", backref="patient", cascade="all, delete-orphan", lazy="dynamic")
    medications = db.relationship("Medication", backref="patient", cascade="all, delete-orphan", lazy="dynamic")
    prescriptions = db.relationship("Prescription", backref="patient", cascade="all, delete-orphan", lazy="dynamic")
    doctor_consents = db.relationship("DoctorPatientConsent", backref="patient", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self, mask_pii=False):
        """Serialize patient with optional PII de-identification."""
        return {
            "id": self.id,
            "chrono_id": self.chrono_id,
            "full_name": "[PROTECTED - PII MASKED]" if mask_pii else self.full_name,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "biological_sex": self.biological_sex,
            "blood_group": self.blood_group,
            "created_at": self.created_at.isoformat(),
        }


class CanonicalMarker(db.Model):
    __tablename__ = "canonical_markers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)  # e.g., 'FASTING_GLUCOSE', 'HBA1C'
    name = db.Column(db.String(100), nullable=False)                           # Display name: 'Fasting Blood Glucose'
    panel = db.Column(db.String(50), nullable=False, index=True)              # 'METABOLIC', 'LIPID', 'RENAL', 'HEPATIC'
    canonical_unit = db.Column(db.String(20), nullable=False)                 # 'mg/dL', 'ng/mL', '%'
    default_min_range = db.Column(db.Float, nullable=True)
    default_max_range = db.Column(db.Float, nullable=True)
    is_higher_better = db.Column(db.Boolean, default=False)                   # e.g. HDL=True, LDL=False

    aliases = db.relationship("MarkerAlias", backref="canonical_marker", cascade="all, delete-orphan")
    test_results = db.relationship("TestResult", backref="canonical_marker", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "panel": self.panel,
            "canonical_unit": self.canonical_unit,
            "default_min_range": self.default_min_range,
            "default_max_range": self.default_max_range,
            "is_higher_better": self.is_higher_better,
        }


class MarkerAlias(db.Model):
    __tablename__ = "marker_aliases"

    id = db.Column(db.Integer, primary_key=True)
    canonical_marker_id = db.Column(db.Integer, db.ForeignKey("canonical_markers.id", ondelete="CASCADE"), nullable=False)
    raw_alias_string = db.Column(db.String(150), unique=True, nullable=False, index=True)


class LabReport(db.Model):
    __tablename__ = "lab_reports"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    lab_name = db.Column(db.String(100), nullable=False)
    test_date = db.Column(db.Date, nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    results = db.relationship("TestResult", backref="report", cascade="all, delete-orphan")


class TestResult(db.Model):
    __tablename__ = "test_results"

    id = db.Column(db.Integer, primary_key=True)
    lab_report_id = db.Column(db.Integer, db.ForeignKey("lab_reports.id", ondelete="CASCADE"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_marker_id = db.Column(db.Integer, db.ForeignKey("canonical_markers.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Raw data extracted from PDF
    raw_marker_name = db.Column(db.String(150), nullable=False)
    raw_value = db.Column(db.Float, nullable=False)
    raw_unit = db.Column(db.String(30), nullable=False)
    lab_min_range = db.Column(db.Float, nullable=True)
    lab_max_range = db.Column(db.Float, nullable=True)

    # Normalized Metrics
    normalized_value = db.Column(db.Float, nullable=False)
    normalized_unit = db.Column(db.String(20), nullable=False)
    relative_range_position = db.Column(db.Float, nullable=True)  # RRP % (0%=min, 100%=max)

    # Longitudinal Dynamics (computed across chronological records)
    velocity_delta_per_year = db.Column(db.Float, nullable=True)
    is_adverse_drift = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "canonical_code": self.canonical_marker.code if self.canonical_marker else None,
            "canonical_name": self.canonical_marker.name if self.canonical_marker else None,
            "panel": self.canonical_marker.panel if self.canonical_marker else None,
            "raw_marker_name": self.raw_marker_name,
            "raw_value": self.raw_value,
            "raw_unit": self.raw_unit,
            "lab_min_range": self.lab_min_range,
            "lab_max_range": self.lab_max_range,
            "normalized_value": self.normalized_value,
            "normalized_unit": self.normalized_unit,
            "relative_range_position": self.relative_range_position,
            "velocity_delta_per_year": self.velocity_delta_per_year,
            "is_adverse_drift": self.is_adverse_drift,
        }


class Medication(db.Model):
    __tablename__ = "medications"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    drug_name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50), nullable=False)       # e.g., '500mg', '10mg'
    frequency = db.Column(db.String(50), nullable=False)    # e.g., 'Once daily after dinner'
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "drug_name": self.drug_name,
            "dosage": self.dosage,
            "frequency": self.frequency,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "notes": self.notes,
        }


class Prescription(db.Model):
    __tablename__ = "prescriptions"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    encounter_date = db.Column(db.Date, nullable=False)
    doctor_name = db.Column(db.String(100), nullable=True)
    clinic_or_hospital = db.Column(db.String(150), nullable=True)

    # Confidence Gating
    ocr_confidence_score = db.Column(db.Float, nullable=True)  # e.g. 98.5 (%)
    structured_notes = db.Column(db.Text, nullable=True)       # Populated if confident

    # Snippet Fallback Architecture
    is_handwriting_fallback = db.Column(db.Boolean, default=False)
    snippet_image_path = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "encounter_date": self.encounter_date.isoformat() if self.encounter_date else None,
            "doctor_name": self.doctor_name,
            "clinic_or_hospital": self.clinic_or_hospital,
            "ocr_confidence_score": self.ocr_confidence_score,
            "structured_notes": self.structured_notes,
            "is_handwriting_fallback": self.is_handwriting_fallback,
            "snippet_image_path": self.snippet_image_path,
        }
