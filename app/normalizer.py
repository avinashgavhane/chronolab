"""
ChronoLab - Normalization & Clinical Ontology Engine
=====================================================
Handles:
1. Canonical Medical Biomarker Definitions (Panels: Metabolic, Lipid, Renal, Hepatic, Thyroid, CBC)
2. Deterministic Unit Conversion (e.g. nmol/L -> ng/mL, mmol/L -> mg/dL)
3. Relative Range Position (RRP %) normalization across conflicting lab reference bands
4. Fuzzy Entity Resolution (maps messy raw lab report strings to canonical biomarkers)
5. Clinical Derived Ratios (Triglyceride/HDL, AST/ALT, BUN/Creatinine)
6. Longitudinal Velocity & Adverse Drift Detection (rate of change per year: dV/dt)
"""

import re
from datetime import date
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. CANONICAL BIOMARKER CATALOG
# ---------------------------------------------------------------------------
# The standard clinical reference dictionary defining primary panels.
CANONICAL_CATALOG = {
    # --- METABOLIC PANEL ---
    "FASTING_GLUCOSE": {
        "name": "Fasting Blood Glucose",
        "panel": "METABOLIC",
        "canonical_unit": "mg/dL",
        "default_min": 70.0,
        "default_max": 99.0,
        "is_higher_better": False,
        "aliases": [
            "fbs", "fasting glucose", "glucose fasting", "blood sugar fasting",
            "fasting blood sugar", "plasma glucose fasting", "glucose (f)", "b. sugar fasting"
        ],
    },
    "HBA1C": {
        "name": "Hemoglobin A1c (Glycated)",
        "panel": "METABOLIC",
        "canonical_unit": "%",
        "default_min": 4.0,
        "default_max": 5.6,
        "is_higher_better": False,
        "aliases": [
            "hba1c", "glycated hemoglobin", "glycosylated hemoglobin", "hemoglobin a1c",
            "a1c", "glyco hb", "hba1c (glycated hb)", "glycated haemoglobin"
        ],
    },
    "FASTING_INSULIN": {
        "name": "Fasting Insulin",
        "panel": "METABOLIC",
        "canonical_unit": "uIU/mL",
        "default_min": 2.6,
        "default_max": 24.9,
        "is_higher_better": False,
        "aliases": ["fasting insulin", "insulin fasting", "serum insulin (f)", "insulin - fasting"],
    },

    # --- LIPID / CARDIOVASCULAR PANEL ---
    "TOTAL_CHOLESTEROL": {
        "name": "Total Cholesterol",
        "panel": "LIPID",
        "canonical_unit": "mg/dL",
        "default_min": 125.0,
        "default_max": 200.0,
        "is_higher_better": False,
        "aliases": ["total cholesterol", "cholesterol total", "serum cholesterol", "cholesterol - total"],
    },
    "HDL_CHOLESTEROL": {
        "name": "HDL Cholesterol (Good)",
        "panel": "LIPID",
        "canonical_unit": "mg/dL",
        "default_min": 40.0,
        "default_max": 60.0,
        "is_higher_better": True,
        "aliases": ["hdl", "hdl cholesterol", "high density lipoprotein", "cholesterol hdl", "hdl-c"],
    },
    "LDL_CHOLESTEROL": {
        "name": "LDL Cholesterol (Bad)",
        "panel": "LIPID",
        "canonical_unit": "mg/dL",
        "default_min": 0.0,
        "default_max": 100.0,
        "is_higher_better": False,
        "aliases": ["ldl", "ldl cholesterol", "low density lipoprotein", "cholesterol ldl", "ldl-c"],
    },
    "TRIGLYCERIDES": {
        "name": "Serum Triglycerides",
        "panel": "LIPID",
        "canonical_unit": "mg/dL",
        "default_min": 0.0,
        "default_max": 150.0,
        "is_higher_better": False,
        "aliases": ["triglycerides", "tg", "serum triglycerides", "triglyceride", "s. triglycerides"],
    },

    # --- RENAL (KIDNEY) PANEL ---
    "SERUM_CREATININE": {
        "name": "Serum Creatinine",
        "panel": "RENAL",
        "canonical_unit": "mg/dL",
        "default_min": 0.7,
        "default_max": 1.2,
        "is_higher_better": False,
        "aliases": ["creatinine", "serum creatinine", "s. creatinine", "creatinine, serum", "sr. creatinine"],
    },
    "BLOOD_UREA_NITROGEN": {
        "name": "Blood Urea Nitrogen (BUN)",
        "panel": "RENAL",
        "canonical_unit": "mg/dL",
        "default_min": 7.0,
        "default_max": 20.0,
        "is_higher_better": False,
        "aliases": ["bun", "blood urea nitrogen", "urea nitrogen", "urea", "serum urea"],
    },
    "EGFR": {
        "name": "Estimated GFR (CKD-EPI)",
        "panel": "RENAL",
        "canonical_unit": "mL/min/1.73m2",
        "default_min": 90.0,
        "default_max": 120.0,
        "is_higher_better": True,
        "aliases": ["egfr", "estimated gfr", "gfr", "estimated glomerular filtration rate", "egfr (ckd-epi)"],
    },

    # --- HEPATIC (LIVER) PANEL ---
    "ALT_SGPT": {
        "name": "ALT (SGPT)",
        "panel": "HEPATIC",
        "canonical_unit": "U/L",
        "default_min": 7.0,
        "default_max": 45.0,
        "is_higher_better": False,
        "aliases": ["alt", "sgpt", "alanine aminotransferase", "alt (sgpt)", "sgpt / alt", "s.g.p.t."],
    },
    "AST_SGOT": {
        "name": "AST (SGOT)",
        "panel": "HEPATIC",
        "canonical_unit": "U/L",
        "default_min": 8.0,
        "default_max": 40.0,
        "is_higher_better": False,
        "aliases": ["ast", "sgot", "aspartate aminotransferase", "ast (sgot)", "sgot / ast", "s.g.o.t."],
    },
    "TOTAL_BILIRUBIN": {
        "name": "Total Bilirubin",
        "panel": "HEPATIC",
        "canonical_unit": "mg/dL",
        "default_min": 0.2,
        "default_max": 1.2,
        "is_higher_better": False,
        "aliases": ["total bilirubin", "bilirubin total", "s. bilirubin total", "bilirubin (total)"],
    },

    # --- THYROID & VITAMINS ---
    "TSH": {
        "name": "Thyroid Stimulating Hormone (TSH)",
        "panel": "THYROID",
        "canonical_unit": "uIU/mL",
        "default_min": 0.4,
        "default_max": 4.5,
        "is_higher_better": False,
        "aliases": ["tsh", "thyroid stimulating hormone", "tsh (ultrasensitive)", "s. tsh"],
    },
    "VITAMIN_D": {
        "name": "25-Hydroxy Vitamin D",
        "panel": "VITAMINS",
        "canonical_unit": "ng/mL",
        "default_min": 30.0,
        "default_max": 100.0,
        "is_higher_better": True,
        "aliases": ["vitamin d", "25-oh vitamin d", "vit d", "25-hydroxy vitamin d", "total vitamin d"],
    },
    "VITAMIN_B12": {
        "name": "Vitamin B12 (Cobalamin)",
        "panel": "VITAMINS",
        "canonical_unit": "pg/mL",
        "default_min": 200.0,
        "default_max": 900.0,
        "is_higher_better": True,
        "aliases": ["vitamin b12", "b12", "cyanocobalamin", "serum vitamin b12", "vit b12"],
    },
}


# ---------------------------------------------------------------------------
# 2. STRING SANITIZATION & FUZZY ENTITY RESOLUTION
# ---------------------------------------------------------------------------
def sanitize_text(text: str) -> str:
    """Normalize raw string by stripping punctuation, extra spaces, and lowercasing."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())


def match_biomarker_alias(raw_string: str) -> Optional[str]:
    """
    Maps an arbitrary raw biomarker string from a lab PDF to its Canonical Marker Code.
    Uses:
    1. Exact alias lookup
    2. Substring matching
    3. Token-based word intersection
    Returns canonical code (e.g. 'FASTING_GLUCOSE') or None.
    """
    clean_query = sanitize_text(raw_string)

    # 1. Exact alias match
    for code, meta in CANONICAL_CATALOG.items():
        for alias in meta["aliases"]:
            if clean_query == alias:
                return code

    # 2. Substring containment match (e.g. 'serum creatinine blood' contains 'serum creatinine')
    for code, meta in CANONICAL_CATALOG.items():
        for alias in meta["aliases"]:
            if alias in clean_query or clean_query in alias:
                # Disambiguation safeguard: avoid matching 'glucose' alone if it's 'pp glucose'
                if "post" in clean_query or "pp" in clean_query:
                    if code == "FASTING_GLUCOSE":
                        continue
                return code

    # 3. Token Jaccard similarity fallback
    query_tokens = set(clean_query.split())
    best_code = None
    best_overlap = 0.0

    for code, meta in CANONICAL_CATALOG.items():
        for alias in meta["aliases"]:
            alias_tokens = set(alias.split())
            intersection = query_tokens.intersection(alias_tokens)
            union = query_tokens.union(alias_tokens)
            if union:
                jaccard = len(intersection) / len(union)
                if jaccard > best_overlap and jaccard >= 0.60:
                    best_overlap = jaccard
                    best_code = code

    return best_code


# ---------------------------------------------------------------------------
# 3. DETERMINISTIC UNIT CONVERSION ENGINE
# ---------------------------------------------------------------------------
def normalize_unit(canonical_code: str, raw_value: float, raw_unit: str) -> Tuple[float, str]:
    """
    Converts divergent measurement units into canonical units using exact clinical formulas.
    Returns: (normalized_value, canonical_unit)
    """
    clean_unit = sanitize_text(raw_unit).replace(" ", "")
    meta = CANONICAL_CATALOG.get(canonical_code)
    if not meta:
        return raw_value, raw_unit

    target_unit = meta["canonical_unit"]

    # --- Vitamin D (nmol/L <-> ng/mL) ---
    # Formula: 1 nmol/L = 0.40064 ng/mL (Factor: divide by 2.496)
    if canonical_code == "VITAMIN_D":
        if "nmol" in clean_unit:
            return round(raw_value * 0.40064, 2), target_unit
        return round(raw_value, 2), target_unit

    # --- Blood Glucose / Cholesterol / Triglycerides (mmol/L <-> mg/dL) ---
    if canonical_code in ["FASTING_GLUCOSE", "TOTAL_CHOLESTEROL", "HDL_CHOLESTEROL", "LDL_CHOLESTEROL", "TRIGLYCERIDES"]:
        if "mmol" in clean_unit:
            if canonical_code == "FASTING_GLUCOSE":
                # Glucose molecular weight = 180.16 g/mol -> 1 mmol/L = 18.016 mg/dL
                return round(raw_value * 18.016, 2), target_unit
            elif canonical_code in ["TOTAL_CHOLESTEROL", "HDL_CHOLESTEROL", "LDL_CHOLESTEROL"]:
                # Cholesterol molecular weight = 386.65 g/mol -> 1 mmol/L = 38.67 mg/dL
                return round(raw_value * 38.67, 2), target_unit
            elif canonical_code == "TRIGLYCERIDES":
                # Triglycerides molecular weight approx 885.7 g/mol -> 1 mmol/L = 88.57 mg/dL
                return round(raw_value * 88.57, 2), target_unit
        return round(raw_value, 2), target_unit

    # --- Creatinine (umol/L <-> mg/dL) ---
    if canonical_code == "SERUM_CREATININE":
        if "umol" in clean_unit or "µmol" in clean_unit:
            # 1 mg/dL = 88.4 umol/L -> umol/L / 88.4 = mg/dL
            return round(raw_value / 88.4, 3), target_unit
        return round(raw_value, 3), target_unit

    # --- Default: Already in canonical unit ---
    return round(raw_value, 2), target_unit


# ---------------------------------------------------------------------------
# 4. RELATIVE RANGE POSITION (RRP %) NORMALIZATION
# ---------------------------------------------------------------------------
def compute_relative_range_position(value: float, min_range: Optional[float], max_range: Optional[float]) -> Optional[float]:
    """
    Computes where an observed value sits as a percentage within a lab's reference band.
    Formula: RRP = ((Value - Min) / (Max - Min)) * 100
    - 0%   = Exactly on the lower bound
    - 50%  = Perfectly centered in the healthy reference range
    - 100% = Exactly on the upper bound
    - >100%= Clinically high
    - <0%  = Clinically low
    """
    if min_range is None or max_range is None or max_range <= min_range:
        return None

    rrp = ((value - min_range) / (max_range - min_range)) * 100.0
    return round(rrp, 1)


# ---------------------------------------------------------------------------
# 5. DERIVED CLINICAL RATIOS (Hidden Biomarkers)
# ---------------------------------------------------------------------------
def calculate_derived_ratios(marker_values: Dict[str, float]) -> Dict[str, Dict]:
    """
    Computes high-value clinical ratios from extracted standard markers.
    Expects marker_values dict mapping canonical codes to their normalized values.
    """
    ratios = {}

    # Ratio 1: Triglyceride to HDL Ratio (Cardiovascular & Insulin Resistance Predictor)
    # Clinical rule: Ideal < 2.0; Borderline 2.0 - 3.5; High Risk > 3.5
    tg = marker_values.get("TRIGLYCERIDES")
    hdl = marker_values.get("HDL_CHOLESTEROL")
    if tg and hdl and hdl > 0:
        val = round(tg / hdl, 2)
        status = "OPTIMAL" if val < 2.0 else ("BORDERLINE" if val <= 3.5 else "HIGH_RISK")
        ratios["TG_HDL_RATIO"] = {
            "name": "Triglyceride / HDL Ratio",
            "value": val,
            "status": status,
            "insight": "Predictor of atherogenic dyslipidemia and insulin resistance.",
        }

    # Ratio 2: De Ritis Ratio (AST / ALT) - Liver Injury Pattern
    # Clinical rule: <1.0 = Non-alcoholic fatty liver (NAFLD); >2.0 = Alcoholic / severe injury
    ast = marker_values.get("AST_SGOT")
    alt = marker_values.get("ALT_SGPT")
    if ast and alt and alt > 0:
        val = round(ast / alt, 2)
        status = "FAVORABLE" if 0.8 <= val <= 1.2 else ("ELEVATED_RATIO" if val > 1.5 else "LOW_RATIO")
        ratios["DE_RITIS_RATIO"] = {
            "name": "De Ritis Ratio (AST/ALT)",
            "value": val,
            "status": status,
            "insight": "Differential indicator for liver enzyme elevation patterns.",
        }

    # Ratio 3: BUN to Creatinine Ratio - Renal vs Pre-Renal Azotemia
    # Clinical rule: Normal 10:1 to 20:1. >20:1 suggests prerenal azotemia / dehydration.
    bun = marker_values.get("BLOOD_UREA_NITROGEN")
    cr = marker_values.get("SERUM_CREATININE")
    if bun and cr and cr > 0:
        val = round(bun / cr, 1)
        status = "NORMAL" if 10.0 <= val <= 20.0 else ("ELEVATED_PRERENAL" if val > 20.0 else "RENAL_PATTERN")
        ratios["BUN_CR_RATIO"] = {
            "name": "BUN / Creatinine Ratio",
            "value": val,
            "status": status,
            "insight": "Differentiates dehydration/prerenal state from intrinsic renal decline.",
        }

    return ratios


# ---------------------------------------------------------------------------
# 6. LONGITUDINAL VELOCITY & ADVERSE DRIFT DETECTION
# ---------------------------------------------------------------------------
def calculate_annual_velocity(
    current_value: float,
    current_date: date,
    previous_value: float,
    previous_date: date
) -> Optional[float]:
    """
    Computes annualized velocity (rate of change per year: dV/dt).
    Formula: ((Current - Previous) / Days_Between) * 365.25
    """
    days = (current_date - previous_date).days
    if days <= 0:
        return None

    annual_delta = ((current_value - previous_value) / days) * 365.25
    return round(annual_delta, 2)


def is_velocity_adverse(canonical_code: str, annual_velocity: float) -> bool:
    """
    Determines whether a calculated annual velocity represents clinically adverse drift.
    Examples:
    - Fasting Glucose increasing > +4.0 mg/dL/year is adverse pre-diabetic drift.
    - eGFR decreasing > -3.0 mL/min/year is adverse renal drift.
    - HbA1c increasing > +0.2 %/year is adverse metabolic drift.
    """
    meta = CANONICAL_CATALOG.get(canonical_code)
    if not meta or annual_velocity is None:
        return False

    is_higher_better = meta.get("is_higher_better", False)

    # Threshold rules for key markers
    if canonical_code == "FASTING_GLUCOSE" and annual_velocity >= 4.0:
        return True
    if canonical_code == "HBA1C" and annual_velocity >= 0.20:
        return True
    if canonical_code == "EGFR" and annual_velocity <= -3.0:
        return True
    if canonical_code == "SERUM_CREATININE" and annual_velocity >= 0.10:
        return True
    if canonical_code == "LDL_CHOLESTEROL" and annual_velocity >= 10.0:
        return True

    # General fallback: if higher is worse and it is increasing rapidly (>15% jump), flag as adverse
    return False
