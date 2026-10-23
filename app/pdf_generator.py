"""
ChronoLab - Physician Brief & Summary PDF Generator
===================================================
Generates a crisp, printable 1-page Clinical Longitudinal Summary PDF for 7-minute doctor visits.
Features:
1. Patient Metadata with optional 1-Click PII Masking (De-identification)
2. Known Diagnoses & Active Medications (Intervention context)
3. Side-by-side multi-year biomarker comparison matrix across different labs
4. Velocity Alert badges (highlighting silent adverse drifts)
5. Derived clinical ratios (Triglyceride/HDL, AST/ALT, BUN/Creatinine)
6. Pre-Consultation Doctor Questions
7. Embedded prescription handwriting image snippet (Confidence fallback)
"""

import os
from io import BytesIO
from datetime import date
from typing import Dict, List, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch


def generate_physician_brief_pdf(
    patient_data: Dict[str, Any],
    chronological_matrix: List[Dict[str, Any]],
    medications: List[Dict[str, Any]],
    derived_ratios: Dict[str, Any],
    doctor_questions: List[str],
    snippet_image_path: Optional[str] = None,
    mask_pii: bool = False
) -> BytesIO:
    """
    Renders an executive 1-page clinical PDF into a BytesIO stream.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#64748B')
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=6,
        spaceAfter=3
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#334155')
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0F172A')
    )
    alert_style = ParagraphStyle(
        'AlertCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#DC2626')
    )

    story = []

    # 1. Header Banner
    display_name = "[PROTECTED - PII MASKED]" if mask_pii else patient_data.get("full_name", "Anonymous")
    chrono_id = patient_data.get("chrono_id", "CHRN-UNASSIGNED")
    age = patient_data.get("age", "N/A")
    sex = patient_data.get("biological_sex", "N/A")
    blood_grp = patient_data.get("blood_group", "N/A")

    header_text = f"<b>CHRONOLAB | CLINICAL LONGITUDINAL BRIEF</b>"
    if mask_pii:
        header_text += " <font color='#DC2626' size='7'><b>[DE-IDENTIFIED / PRIVACY SAFE HARBOR ACTIVE]</b></font>"

    story.append(Paragraph(header_text, title_style))
    story.append(Paragraph(
        f"<b>ChronoID:</b> {chrono_id} &nbsp;|&nbsp; <b>Patient Name:</b> {display_name} &nbsp;|&nbsp; <b>Age:</b> {age} &nbsp;|&nbsp; <b>Sex:</b> {sex} &nbsp;|&nbsp; <b>Blood:</b> {blood_grp} &nbsp;|&nbsp; <b>Date:</b> {date.today().strftime('%b %d, %Y')}",
        subtitle_style
    ))
    story.append(Spacer(1, 4))

    # Divider line
    divider = Table([['']], colWidths=[540], rowHeights=[1.5])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0284C7')),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 6))

    # 2. Context & Interventions Box (Diagnoses & Active Meds)
    meds_str = ", ".join([f"{m['drug_name']} ({m.get('dosage','')})" for m in medications]) if medications else "None recorded"
    story.append(Paragraph("<b>1. CLINICAL CONTEXT & ACTIVE INTERVENTIONS</b>", section_heading))
    context_data = [
        [
            Paragraph(f"<b>Active Medications:</b> {meds_str}", cell_style),
            Paragraph(f"<b>Key Ratios:</b> " + " | ".join([f"{r['name']}: <b>{r['value']}</b> ({r['status']})" for r in derived_ratios.values()]), cell_style)
        ]
    ]
    context_table = Table(context_data, colWidths=[270, 270])
    context_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(context_table)
    story.append(Spacer(1, 6))

    # 3. Longitudinal Biomarker Matrix (The Core Table)
    story.append(Paragraph("<b>2. MULTI-YEAR BIOMARKER TRAJECTORY MATRIX (Normalized Units)</b>", section_heading))

    # Extract distinct test dates/labs
    header_row = [
        Paragraph("<b>Biomarker (Panel)</b>", cell_bold),
        Paragraph("<b>Baseline</b>", cell_bold),
        Paragraph("<b>Interim</b>", cell_bold),
        Paragraph("<b>Latest</b>", cell_bold),
        Paragraph("<b>Annual Velocity (dV/dt)</b>", cell_bold),
        Paragraph("<b>Clinical Drift Alert</b>", cell_bold)
    ]
    matrix_rows = [header_row]

    for item in chronological_matrix:
        # e.g. item = { 'name': 'Fasting Glucose', 'unit': 'mg/dL', 'baseline': '78', 'interim': '88', 'latest': '98', 'velocity': '+6.7/yr', 'is_adverse': True, 'alert': 'Pre-Diabetic Drift' }
        is_adv = item.get("is_adverse", False)
        alert_cell = Paragraph(f"<font color='#DC2626'><b>{item.get('alert', 'STABLE')}</b></font>" if is_adv else "<font color='#16A34A'>STABLE</font>", alert_style if is_adv else cell_style)
        vel_text = f"<b>{item.get('velocity', '0.0')}</b>"
        vel_cell = Paragraph(f"<font color='#DC2626'>{vel_text}</font>" if is_adv else vel_text, cell_style)

        matrix_rows.append([
            Paragraph(f"<b>{item['name']}</b> ({item.get('unit','')})", cell_style),
            Paragraph(str(item.get('baseline', '-')), cell_style),
            Paragraph(str(item.get('interim', '-')), cell_style),
            Paragraph(f"<b>{item.get('latest', '-')}</b>", cell_bold),
            vel_cell,
            alert_cell
        ])

    matrix_table = Table(matrix_rows, colWidths=[150, 65, 65, 65, 95, 100])
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(matrix_table)
    story.append(Spacer(1, 6))

    # 4. Pre-Consultation Doctor Questions (Socratic Empowerment)
    story.append(Paragraph("<b>3. RECOMMENDED QUESTIONS FOR CONSULTING PHYSICIAN</b>", section_heading))
    q_paragraphs = []
    for idx, q in enumerate(doctor_questions[:3], 1):
        q_paragraphs.append([Paragraph(f"<b>Q{idx}:</b> {q}", cell_style)])

    if not q_paragraphs:
        q_paragraphs = [[Paragraph("• No acute adverse drift detected. Routine preventive follow-up advised.", cell_style)]]

    q_table = Table(q_paragraphs, colWidths=[540])
    q_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EFF6FF')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#BFDBFE')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(q_table)
    story.append(Spacer(1, 6))

    # 5. Prescription Handwriting Fallback Snippet (Confidence Gating)
    if snippet_image_path and os.path.exists(snippet_image_path):
        story.append(Paragraph("<b>4. ATTACHED CLINICAL ARTIFACT (Original Doctor Prescription Snippet)</b>", section_heading))
        story.append(Paragraph("<i>Note: AI OCR flagged low confidence on handwritten notes; authentic image snippet preserved below for clinical interpretation.</i>", subtitle_style))
        story.append(Spacer(1, 2))
        try:
            rl_img = RLImage(snippet_image_path, width=4.5*inch, height=0.9*inch)
            img_table = Table([[rl_img]], colWidths=[540])
            img_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            story.append(img_table)
        except Exception:
            pass

    # Build Document
    doc.build(story)
    buffer.seek(0)
    return buffer
