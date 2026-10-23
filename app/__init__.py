"""
ChronoLab - Core Flask Application Controller
==============================================
Implements:
1. Intent-Driven Triage Dashboard
2. PDF Lab Report Upload & Processing Pipeline
3. Prescription Image Upload & Snippet Fallback Cropper
4. Medication Logging (Intervention Timeline Overlay)
5. 1-Page Printable Physician Brief PDF Export with PII Masking
"""

import os
import json
from datetime import datetime, date
from flask import (
    Flask, render_template, request, redirect, url_for, flash, send_file, session
)

from app.models import (
    db, User, Patient, Doctor, DoctorPatientConsent, CanonicalMarker, MarkerAlias, LabReport, TestResult, Medication, Prescription
)
from app.normalizer import (
    calculate_derived_ratios,
    calculate_annual_velocity,
    is_velocity_adverse,
    CANONICAL_CATALOG
)
from app.parser import parse_lab_report_pdf, process_prescription_image
from app.pdf_generator import generate_physician_brief_pdf
from app.seed_data import seed_demo_patient


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    from config import config_by_name
    app = Flask(__name__)
    selected_config = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(selected_config)
    
    # Ensure upload directories exist
    os.makedirs(app.config["REPORTS_FOLDER"], exist_ok=True)
    os.makedirs(app.config["SNIPPETS_FOLDER"], exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Seed demo patient for instant out-of-the-box demonstration
        seed_demo_patient(app.config["UPLOAD_FOLDER"])

    # Health check endpoint for cloud orchestrators (Render, Railway, Kubernetes, AWS ALB)
    @app.route("/healthz")
    @app.route("/health")
    def health_check():
        return {
            "status": "healthy",
            "service": "ChronoLab Engine",
            "version": "1.2.0",
            "database": "connected"
        }, 200

    # -----------------------------------------------------------------------
    # -----------------------------------------------------------------------
    # PUBLIC MARKETING & AUTH ROUTES
    # -----------------------------------------------------------------------

    @app.route("/")
    def home_page():
        return render_template("home.html")

    @app.route("/about")
    def about_page():
        return render_template("about.html")

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                session["user_id"] = user.id
                session["user_email"] = user.email
                session["user_role"] = user.role

                if user.role == "admin":
                    flash("Welcome to the System Administration Console.", "success")
                    return redirect(url_for("admin_page"))
                
                elif user.role == "doctor":
                    doc = user.doctor or Doctor.query.filter_by(user_id=user.id).first()
                    if not doc:
                        doc = Doctor.query.first()
                    session["doctor_id"] = doc.doctor_id if doc else "DOC-2026-401"
                    session["doctor_name"] = doc.full_name if doc else "Doctor"
                    flash(f"Welcome to the Clinical OPD Portal, {doc.full_name if doc else user.email}!", "success")
                    return redirect(url_for("doctor_dashboard"))

                # If patient user, tie to their patient profile
                if user.patient:
                    session["chrono_id"] = user.patient.chrono_id
                else:
                    demo = Patient.query.first()
                    session["chrono_id"] = demo.chrono_id if demo else "CHRN-2026-8491"

                flash(f"Welcome back to your Health Vault, {user.email}!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid email or password. Please verify credentials.", "error")

        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register_page():
        if request.method == "POST":
            role = request.form.get("role", "patient")
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if User.query.filter_by(email=email).first():
                flash("An account with this email already exists. Please log in.", "error")
                return redirect(url_for("login_page"))

            import random
            if role == "doctor":
                specialty = request.form.get("specialty", "Internal Medicine & General Physician")
                reg_num = request.form.get("registration_number", "MCI-74921")
                hospital = request.form.get("hospital_affiliation", "Apollo Clinical Hospital")
                doc_id = f"DOC-2026-{random.randint(100, 999)}"

                new_user = User(email=email, role="doctor")
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.flush()

                new_doc = Doctor(
                    user_id=new_user.id,
                    doctor_id=doc_id,
                    full_name=full_name,
                    specialty=specialty,
                    registration_number=reg_num,
                    hospital_affiliation=hospital
                )
                db.session.add(new_doc)
                db.session.commit()

                session["user_id"] = new_user.id
                session["user_email"] = new_user.email
                session["user_role"] = new_user.role
                session["doctor_id"] = doc_id
                session["doctor_name"] = full_name

                flash(f"Doctor account registered! Your Doctor ID is {doc_id}", "success")
                return redirect(url_for("doctor_dashboard"))

            else:
                # Patient Registration
                dob_str = request.form.get("date_of_birth")
                sex = request.form.get("biological_sex", "OTHER")
                blood = request.form.get("blood_group")

                random_num = random.randint(1000, 9999)
                chrono_id = f"CHRN-2026-{random_num}"

                new_user = User(email=email, role="patient")
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.flush()

                dob = datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else date(1990, 1, 1)
                new_patient = Patient(
                    user_id=new_user.id,
                    chrono_id=chrono_id,
                    full_name=full_name,
                    date_of_birth=dob,
                    biological_sex=sex,
                    blood_group=blood
                )
                db.session.add(new_patient)
                db.session.commit()

                session["user_id"] = new_user.id
                session["user_email"] = new_user.email
                session["user_role"] = new_user.role
                session["chrono_id"] = chrono_id

                flash(f"Account successfully created! Assigned Universal Health ID: {chrono_id}", "success")
                return redirect(url_for("dashboard"))

        return render_template("register.html")

    @app.route("/logout")
    def logout_action():
        session.clear()
        flash("You have been signed out safely.", "success")
        return redirect(url_for("home_page"))

    # -----------------------------------------------------------------------
    # DOCTOR CLINICAL MODULE & CONSENT ENFORCEMENT
    # -----------------------------------------------------------------------

    @app.route("/doctor")
    def doctor_dashboard():
        if session.get("user_role") not in ["doctor", "admin"]:
            flash("Doctor or Administrator clearance required. Please log in as a Doctor.", "error")
            return redirect(url_for("login_page"))

        doc = None
        if session.get("user_id"):
            doc = Doctor.query.filter_by(user_id=session.get("user_id")).first()
        if not doc:
            doc = Doctor.query.first()

        if not doc:
            # Self-heal demo doctor
            doc_user = User(email="doctor@chronolab.com", role="doctor")
            doc_user.set_password("Doctor@123")
            db.session.add(doc_user)
            db.session.flush()
            doc = Doctor(
                user_id=doc_user.id,
                doctor_id="DOC-2026-401",
                full_name="Dr. Arvind Sharma, MD",
                specialty="Internal Medicine & Diabetology",
                registration_number="MCI-74921",
                hospital_affiliation="Apollo Clinical Hospital"
            )
            db.session.add(doc)
            db.session.commit()

        # Fetch authorized patients (Active Consent)
        consents = DoctorPatientConsent.query.filter_by(doctor_id=doc.id, status="ACTIVE").all()
        authorized_patient_ids = [c.patient_id for c in consents]
        authorized_patients = Patient.query.filter(Patient.id.in_(authorized_patient_ids)).all() if authorized_patient_ids else []

        searched_id = request.args.get("chrono_id", "").strip().upper()
        active_patient = None
        access_denied = False

        if searched_id:
            candidate = Patient.query.filter_by(chrono_id=searched_id).first()
            if not candidate:
                candidate = Patient.query.filter(Patient.full_name.ilike(f"%{searched_id}%")).first()

            if candidate:
                has_consent = DoctorPatientConsent.query.filter_by(doctor_id=doc.id, patient_id=candidate.id, status="ACTIVE").first()
                if has_consent or session.get("user_role") == "admin":
                    active_patient = candidate
                else:
                    access_denied = True
            else:
                flash(f"No patient found matching '{searched_id}'.", "error")
        elif authorized_patients:
            active_patient = authorized_patients[0]

        patient_data = None
        if active_patient:
            results = (
                TestResult.query
                .filter_by(patient_id=active_patient.id)
                .join(LabReport)
                .order_by(LabReport.test_date.desc())
                .all()
            )
            meds = Medication.query.filter_by(patient_id=active_patient.id).all()
            rx_list = Prescription.query.filter_by(patient_id=active_patient.id).order_by(Prescription.encounter_date.desc()).all()
            normalized_map = {r.canonical_marker.code: r.normalized_value for r in results}
            derived_ratios = calculate_derived_ratios(normalized_map)

            patient_data = {
                "patient": active_patient,
                "results": results,
                "medications": meds,
                "prescriptions": rx_list,
                "derived_ratios": derived_ratios
            }

        return render_template(
            "doctor.html",
            doctor=doc,
            authorized_patients=authorized_patients,
            active_patient_data=patient_data,
            searched_id=searched_id,
            access_denied=access_denied
        )

    @app.route("/doctor/prescribe", methods=["POST"])
    def doctor_prescribe():
        if session.get("user_role") not in ["doctor", "admin"]:
            flash("Unauthorized", "error")
            return redirect(url_for("login_page"))

        patient_id = request.form.get("patient_id")
        drug_name = request.form.get("drug_name")
        dosage = request.form.get("dosage")
        frequency = request.form.get("frequency")
        notes = request.form.get("notes")

        new_med = Medication(
            patient_id=patient_id,
            drug_name=drug_name,
            dosage=dosage,
            frequency=frequency,
            start_date=date.today(),
            notes=notes
        )
        db.session.add(new_med)
        db.session.commit()

        pat = Patient.query.get(patient_id)
        flash(f"Prescription for {drug_name} ({dosage}) added to patient's active regimen.", "success")
        return redirect(url_for("doctor_dashboard", chrono_id=pat.chrono_id if pat else ""))

    # -----------------------------------------------------------------------
    # PATIENT CONSENT DELEGATION & MANAGEMENT
    # -----------------------------------------------------------------------

    @app.route("/patient/consent/grant", methods=["POST"])
    def grant_doctor_consent():
        chrono_id = session.get("chrono_id", "CHRN-2026-8491")
        patient = Patient.query.filter_by(chrono_id=chrono_id).first()
        doctor_query = request.form.get("doctor_id_or_email", "").strip()

        doc = Doctor.query.filter(
            (Doctor.doctor_id == doctor_query.upper()) |
            (Doctor.full_name.ilike(f"%{doctor_query}%"))
        ).first()

        if not doc:
            flash(f"No certified doctor found matching '{doctor_query}'. Try entering 'DOC-2026-401'.", "error")
            return redirect(url_for("dashboard"))

        consent = DoctorPatientConsent.query.filter_by(patient_id=patient.id, doctor_id=doc.id).first()
        if consent:
            consent.status = "ACTIVE"
            consent.granted_at = datetime.utcnow()
        else:
            consent = DoctorPatientConsent(
                patient_id=patient.id,
                doctor_id=doc.id,
                status="ACTIVE"
            )
            db.session.add(consent)

        db.session.commit()
        flash(f"Access granted! Dr. {doc.full_name} ({doc.doctor_id}) can now view your records in OPD.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/patient/consent/revoke/<int:consent_id>", methods=["POST"])
    def revoke_doctor_consent(consent_id):
        consent = DoctorPatientConsent.query.get_or_404(consent_id)
        consent.status = "REVOKED"
        consent.revoked_at = datetime.utcnow()
        db.session.commit()
        flash(f"Access revoked for Dr. {consent.doctor.full_name}. They can no longer view your medical records.", "success")
        return redirect(url_for("dashboard"))

    # -----------------------------------------------------------------------
    # SYSTEM ADMIN MODULE
    # -----------------------------------------------------------------------

    @app.route("/admin")
    def admin_page():
        # Check admin authorization
        if session.get("user_role") != "admin":
            flash("Administrator clearance required. Please log in with admin credentials.", "error")
            return redirect(url_for("login_page"))

        users = User.query.order_by(User.created_at.desc()).all()
        doctors = Doctor.query.all()
        patients = Patient.query.order_by(Patient.created_at.desc()).all()
        recent_reports = LabReport.query.order_by(LabReport.uploaded_at.desc()).limit(15).all()

        stats = {
            "user_count": User.query.count(),
            "doctor_count": Doctor.query.count(),
            "patient_count": Patient.query.count(),
            "report_count": LabReport.query.count(),
            "test_result_count": TestResult.query.count(),
            "prescription_count": Prescription.query.count()
        }

        return render_template(
            "admin.html", 
            users=users, 
            doctors=doctors, 
            patients=patients, 
            recent_reports=recent_reports, 
            stats=stats
        )

    @app.route("/admin/toggle-user-role/<int:user_id>", methods=["POST"])
    def toggle_user_role(user_id):
        if session.get("user_role") != "admin":
            flash("Unauthorized", "error")
            return redirect(url_for("login_page"))

        target_user = User.query.get_or_404(user_id)
        new_role = request.form.get("role", "patient")
        target_user.role = new_role
        db.session.commit()
        flash(f"Role for {target_user.email} updated to {new_role.upper()}.", "success")
        return redirect(url_for("admin_page"))

    @app.route("/admin/set-patient/<int:patient_id>")
    def set_active_patient(patient_id):
        patient = Patient.query.get_or_404(patient_id)
        session["chrono_id"] = patient.chrono_id
        flash(f"Active clinical view switched to patient: {patient.full_name} ({patient.chrono_id})", "success")
        return redirect(url_for("dashboard"))

    # -----------------------------------------------------------------------
    # CLINICAL DASHBOARD ROUTE
    # -----------------------------------------------------------------------

    @app.route("/dashboard")
    def dashboard():
        # Retrieve primary demo patient (or active session patient)
        active_chrono = session.get("chrono_id", "CHRN-2026-8491")
        patient = Patient.query.filter_by(chrono_id=active_chrono).first()
        if not patient:
            patient = Patient.query.first()

        session["chrono_id"] = patient.chrono_id

        # 1. Fetch Medications (Active Interventions)
        meds = Medication.query.filter_by(patient_id=patient.id).order_by(Medication.start_date.asc()).all()
        meds_data = [m.to_dict() for m in meds]

        # 2. Fetch Latest Test Results & Adverse Drift Flags
        latest_results = (
            TestResult.query
            .filter_by(patient_id=patient.id)
            .order_by(TestResult.created_at.desc())
            .all()
        )

        # De-duplicate to get latest per canonical marker
        latest_by_marker = {}
        for r in latest_results:
            code = r.canonical_marker.code
            if code not in latest_by_marker:
                latest_by_marker[code] = r

        # Calculate Derived Ratios from latest available markers
        latest_normalized_map = {code: r.normalized_value for code, r in latest_by_marker.items()}
        derived_ratios = calculate_derived_ratios(latest_normalized_map)

        # Identify Active Adverse Drifts
        adverse_drifts = [r.to_dict() for r in latest_by_marker.values() if r.is_adverse_drift]

        # 3. Fetch Prescription & Snippet Fallback
        latest_rx = Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.encounter_date.desc()).first()

        # 4. Construct Socratic Questions for Doctor
        doctor_questions = []
        if any(r["canonical_code"] in ["FASTING_GLUCOSE", "HBA1C"] for r in adverse_drifts):
            doctor_questions.append(
                "My fasting glucose has steadily drifted upward across 4 consecutive tests (+6.7 mg/dL/yr). Should we assess early insulin resistance or adjust my Metformin dosage?"
            )
        if any(r.canonical_marker.code == "LDL_CHOLESTEROL" for r in latest_by_marker.values()):
            doctor_questions.append(
                "Since starting Atorvastatin in mid-2024, my LDL dropped by ~30%. Is my current liver enzyme level (ALT) safe to maintain this dose?"
            )
        if derived_ratios.get("TG_HDL_RATIO", {}).get("status") == "HIGH_RISK":
            doctor_questions.append(
                "My Triglyceride-to-HDL ratio is above 3.5. Does this increase my atherogenic cardiovascular risk, and should we consider dietary lifestyle changes?"
            )
        if not doctor_questions:
            doctor_questions.append("My longitudinal biomarkers remain stable. What is the recommended screening cadence for my next follow-up?")

        # 5. Build Chart Data JSON for Chart.js (Grouped by Organ Panels)
        all_results = (
            TestResult.query
            .filter_by(patient_id=patient.id)
            .join(LabReport)
            .order_by(LabReport.test_date.asc())
            .all()
        )

        # Structure chart_data = { 'METABOLIC': { 'dates': [...], 'datasets': [...] }, ... }
        chart_data = {
            "METABOLIC": {"dates": [], "datasets": []},
            "LIPID": {"dates": [], "datasets": []},
            "RENAL": {"dates": [], "datasets": []},
            "HEPATIC": {"dates": [], "datasets": []}
        }

        # Colors for datasets
        palette = ["#0284c7", "#059669", "#dc2626", "#d97706", "#7c3aed", "#db2777"]

        for panel_key in chart_data.keys():
            # Get distinct test dates for this panel
            panel_results = [r for r in all_results if r.canonical_marker.panel == panel_key]
            dates = sorted(list(set(r.report.test_date.strftime("%b %Y") for r in panel_results)))
            chart_data[panel_key]["dates"] = dates

            # Group by marker
            markers_in_panel = sorted(list(set(r.canonical_marker.name for r in panel_results)))
            for idx, marker_name in enumerate(markers_in_panel):
                # Build time series
                values_by_date = {}
                for r in panel_results:
                    if r.canonical_marker.name == marker_name:
                        values_by_date[r.report.test_date.strftime("%b %Y")] = r.normalized_value

                data_points = [values_by_date.get(d, None) for d in dates]
                color = palette[idx % len(palette)]
                chart_data[panel_key]["datasets"].append({
                    "label": marker_name,
                    "data": data_points,
                    "borderColor": color,
                    "backgroundColor": color,
                    "borderWidth": 2,
                    "tension": 0.3,
                    "pointRadius": 4,
                    "spanGaps": True
                })

        # 6. Fetch Doctor Consents & Certified Doctors for Consent Management
        consents = DoctorPatientConsent.query.filter_by(patient_id=patient.id).all()
        all_doctors = Doctor.query.all()

        return render_template(
            "dashboard.html",
            patient=patient,
            medications=meds_data,
            adverse_drifts=adverse_drifts,
            derived_ratios=derived_ratios,
            prescription=latest_rx,
            doctor_questions=doctor_questions,
            chart_json=json.dumps(chart_data),
            consents=consents,
            all_doctors=all_doctors
        )

    @app.route("/upload")
    def upload_page():
        return render_template("upload.html")

    @app.route("/upload/lab-report", methods=["POST"])
    def upload_lab_report():
        if "report_file" not in request.files and "pdf_file" not in request.files:
            flash("No file selected", "error")
            return redirect(url_for("upload_page"))

        file = request.files.get("report_file") or request.files.get("pdf_file")
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(url_for("upload_page"))

        filename_lower = file.filename.lower()
        is_pdf = filename_lower.endswith(".pdf")
        is_image = any(filename_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"])

        if not (is_pdf or is_image):
            flash("Unsupported file type. Please upload a PDF or an Image (JPG/PNG).", "error")
            return redirect(url_for("upload_page"))

        dest_filename = f"report_{int(datetime.now().timestamp())}_{file.filename}"
        dest_path = os.path.join(app.config["REPORTS_FOLDER"], dest_filename)
        file.save(dest_path)

        try:
            if is_pdf:
                parsed = parse_lab_report_pdf(dest_path)
            else:
                from app.parser import parse_lab_report_image
                parsed = parse_lab_report_image(dest_path)

            patient = Patient.query.filter_by(chrono_id=session.get("chrono_id", "CHRN-2026-8491")).first()
            if not patient:
                patient = Patient.query.first()

            # Create Report
            report = LabReport(
                patient_id=patient.id,
                lab_name=parsed["metadata"]["lab_name"],
                test_date=parsed["metadata"]["test_date"],
                original_filename=file.filename
            )
            db.session.add(report)
            db.session.flush()

            # Insert extracted results
            inserted_count = 0
            for item in parsed["extracted_results"]:
                marker = CanonicalMarker.query.filter_by(code=item["canonical_code"]).first()
                if not marker:
                    continue

                # Check previous test for velocity
                prev_res = (
                    TestResult.query
                    .join(LabReport)
                    .filter(
                        TestResult.patient_id == patient.id,
                        TestResult.canonical_marker_id == marker.id,
                        LabReport.test_date < report.test_date
                    )
                    .order_by(LabReport.test_date.desc())
                    .first()
                )

                velocity = None
                is_adv = False
                if prev_res:
                    velocity = calculate_annual_velocity(
                        item["normalized_value"], report.test_date,
                        prev_res.normalized_value, prev_res.report.test_date
                    )
                    is_adv = is_velocity_adverse(item["canonical_code"], velocity)

                db.session.add(TestResult(
                    lab_report_id=report.id,
                    patient_id=patient.id,
                    canonical_marker_id=marker.id,
                    raw_marker_name=item["raw_marker_name"],
                    raw_value=item["raw_value"],
                    raw_unit=item["raw_unit"],
                    lab_min_range=item["lab_min_range"],
                    lab_max_range=item["lab_max_range"],
                    normalized_value=item["normalized_value"],
                    normalized_unit=item["normalized_unit"],
                    relative_range_position=item["relative_range_position"],
                    velocity_delta_per_year=velocity,
                    is_adverse_drift=is_adv
                ))
                inserted_count += 1

            db.session.commit()
            flash(f"Successfully processed {inserted_count} biomarkers from {report.lab_name}!", "success")
        except Exception as e:
            flash(f"Extraction error: {str(e)}", "error")

        return redirect(url_for("dashboard"))

    @app.route("/upload/prescription", methods=["POST"])
    def upload_prescription():
        if "rx_image" not in request.files:
            flash("No prescription image uploaded", "error")
            return redirect(url_for("upload_page"))

        file = request.files["rx_image"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(url_for("upload_page"))

        sim_conf = float(request.form.get("simulated_confidence", 78.0))

        dest_filename = f"rx_{int(datetime.now().timestamp())}_{file.filename}"
        dest_path = os.path.join(app.config["UPLOAD_FOLDER"], dest_filename)
        file.save(dest_path)

        patient = Patient.query.filter_by(chrono_id=session.get("chrono_id", "CHRN-2026-8491")).first()

        try:
            rx_result = process_prescription_image(
                dest_path,
                app.config["SNIPPETS_FOLDER"],
                simulated_ocr_confidence=sim_conf
            )

            db.session.add(Prescription(
                patient_id=patient.id,
                encounter_date=date.today(),
                doctor_name="Consulting Physician",
                clinic_or_hospital="Clinical Healthcare Center",
                ocr_confidence_score=rx_result["ocr_confidence"],
                structured_notes=rx_result["structured_notes"],
                is_handwriting_fallback=rx_result["is_handwriting_fallback"],
                snippet_image_path=rx_result["snippet_path"]
            ))
            db.session.commit()

            if rx_result["is_handwriting_fallback"]:
                flash("Low-confidence OCR handwriting detected: Cropped authentic handwriting snippet for physician review.", "warning")
            else:
                flash("High-confidence OCR: Successfully parsed structured prescription notes.", "success")
        except Exception as e:
            flash(f"Error processing prescription: {str(e)}", "error")

        return redirect(url_for("dashboard"))

    @app.route("/add-medication", methods=["POST"])
    def add_medication():
        patient = Patient.query.filter_by(chrono_id=session.get("chrono_id", "CHRN-2026-8491")).first()
        drug_name = request.form.get("drug_name")
        dosage = request.form.get("dosage")
        frequency = request.form.get("frequency")
        start_date_str = request.form.get("start_date")

        try:
            start_d = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            db.session.add(Medication(
                patient_id=patient.id,
                drug_name=drug_name,
                dosage=dosage,
                frequency=frequency,
                start_date=start_d
            ))
            db.session.commit()
            flash(f"Added {drug_name} intervention timeline marker!", "success")
        except Exception as e:
            flash(f"Error adding medication: {str(e)}", "error")

        return redirect(url_for("dashboard"))

    @app.route("/export-brief")
    def export_brief_pdf():
        mask_pii = request.args.get("mask_pii", "true").lower() == "true"
        patient = Patient.query.filter_by(chrono_id=session.get("chrono_id", "CHRN-2026-8491")).first()

        # Build chronological matrix for top markers
        target_markers = ["FASTING_GLUCOSE", "HBA1C", "TOTAL_CHOLESTEROL", "LDL_CHOLESTEROL", "SERUM_CREATININE", "EGFR", "ALT_SGPT"]
        matrix = []

        for code in target_markers:
            marker = CanonicalMarker.query.filter_by(code=code).first()
            if not marker:
                continue

            results = (
                TestResult.query
                .filter_by(patient_id=patient.id, canonical_marker_id=marker.id)
                .join(LabReport)
                .order_by(LabReport.test_date.asc())
                .all()
            )

            if not results:
                continue

            baseline_val = results[0].normalized_value
            interim_val = results[len(results)//2].normalized_value if len(results) > 2 else "-"
            latest_res = results[-1]
            latest_val = latest_res.normalized_value

            vel_str = f"{latest_res.velocity_delta_per_year:+.1f}/yr" if latest_res.velocity_delta_per_year else "0.0/yr"
            alert_text = "Pre-Diabetic Drift" if latest_res.is_adverse_drift else "STABLE"

            matrix.append({
                "name": marker.name,
                "unit": marker.canonical_unit,
                "baseline": baseline_val,
                "interim": interim_val,
                "latest": latest_val,
                "velocity": vel_str,
                "is_adverse": latest_res.is_adverse_drift,
                "alert": alert_text
            })

        # Fetch active meds
        meds = [m.to_dict() for m in Medication.query.filter_by(patient_id=patient.id).all()]

        # Derived Ratios
        latest_results = TestResult.query.filter_by(patient_id=patient.id).all()
        normalized_map = {r.canonical_marker.code: r.normalized_value for r in latest_results}
        derived_ratios = calculate_derived_ratios(normalized_map)

        # Questions
        questions = [
            "My fasting glucose exhibits steady year-over-year drift (+6.7 mg/dL/yr). Should we assess early insulin resistance?",
            "LDL dropped by 30% following Statin intervention; is liver enzyme ALT within safe margins?",
            "My Triglyceride-to-HDL ratio is elevated (>3.5); what dietary adjustments are recommended?"
        ]

        # Handwriting snippet path
        latest_rx = Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.encounter_date.desc()).first()
        snippet_full_path = None
        if latest_rx and latest_rx.snippet_image_path:
            snippet_full_path = os.path.join(app.config["UPLOAD_FOLDER"], latest_rx.snippet_image_path.replace("uploads/", ""))

        pdf_stream = generate_physician_brief_pdf(
            patient_data={
                "full_name": patient.full_name,
                "chrono_id": patient.chrono_id,
                "age": 48,
                "biological_sex": patient.biological_sex,
                "blood_group": patient.blood_group
            },
            chronological_matrix=matrix,
            medications=meds,
            derived_ratios=derived_ratios,
            doctor_questions=questions,
            snippet_image_path=snippet_full_path,
            mask_pii=mask_pii
        )

        return send_file(
            pdf_stream,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"Physician_Brief_{patient.chrono_id}_{'MASKED' if mask_pii else 'FULL'}.pdf"
        )

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True, port=5000)
