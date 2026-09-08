"""
Legal Metrology (Packaged Commodities) Rules, 2011 — Codified Rules Engine.

Contains all mandatory declaration requirements, font size tables,
MRP format rules, and validation helpers as per the latest amendments
(including 2024-2026 updates).
"""

import re
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Rule 6: Mandatory Declarations
# ---------------------------------------------------------------------------
MANDATORY_DECLARATIONS = {
    "R6_1_A_NAME": {
        "rule_id": "R6_1_A_NAME",
        "rule_name": "Manufacturer / Packer / Importer Name",
        "rule_reference": "Rule 6(1)(a)",
        "description": (
            "The name of the manufacturer, or the packer, or the importer, "
            "as the case may be, shall be declared on the package."
        ),
        "severity": "critical",
        "field_key": "manufacturer_name",
    },
    "R6_1_A_ADDR": {
        "rule_id": "R6_1_A_ADDR",
        "rule_name": "Manufacturer / Packer / Importer Address",
        "rule_reference": "Rule 6(1)(a)",
        "description": (
            "The complete address of the manufacturer, packer, or importer "
            "must be declared on the package."
        ),
        "severity": "critical",
        "field_key": "manufacturer_address",
    },
    "R6_1_B": {
        "rule_id": "R6_1_B",
        "rule_name": "Common / Generic Name of Commodity",
        "rule_reference": "Rule 6(1)(b)",
        "description": (
            "The common or generic name of the commodity contained in the "
            "package shall be mentioned."
        ),
        "severity": "high",
        "field_key": "product_name",
    },
    "R6_1_C": {
        "rule_id": "R6_1_C",
        "rule_name": "Net Quantity",
        "rule_reference": "Rule 6(1)(c)",
        "description": (
            "The net quantity of the commodity in terms of standard units of "
            "weight, measure or number shall be declared."
        ),
        "severity": "critical",
        "field_key": "net_quantity",
    },
    "R6_1_D": {
        "rule_id": "R6_1_D",
        "rule_name": "Month & Year of Manufacture / Packing / Import",
        "rule_reference": "Rule 6(1)(d)",
        "description": (
            "The month and year in which the commodity is manufactured, "
            "packed, or imported shall be mentioned."
        ),
        "severity": "high",
        "field_key": "manufacture_date",
    },
    "R6_1_E": {
        "rule_id": "R6_1_E",
        "rule_name": "Maximum Retail Price (MRP)",
        "rule_reference": "Rule 6(1)(e)",
        "description": (
            "The retail sale price of the package inclusive of all taxes, "
            "declared as 'MRP Rs. _____ (inclusive of all taxes)'."
        ),
        "severity": "critical",
        "field_key": "mrp",
    },
    "R6_1_F": {
        "rule_id": "R6_1_F",
        "rule_name": "Consumer Care Details",
        "rule_reference": "Rule 6(1)(f)",
        "description": (
            "The name, address, telephone number and e-mail address of the "
            "person or office who can be contacted in case of consumer complaint."
        ),
        "severity": "high",
        "field_key": "consumer_care",
    },
    "R6_1_G": {
        "rule_id": "R6_1_G",
        "rule_name": "Country of Origin (Imported Goods)",
        "rule_reference": "Rule 6(1)(g)",
        "description": (
            "For imported products, the country of origin must be declared."
        ),
        "severity": "high",
        "field_key": "country_of_origin",
    },
}

# ---------------------------------------------------------------------------
# Rule 7: Font Size Requirements (Table I)
# Minimum height of numerals and letters based on PDP area
# ---------------------------------------------------------------------------
FONT_SIZE_TABLE: List[Dict] = [
    {"pdp_min_cm2": 0, "pdp_max_cm2": 50, "min_height_mm": 1},
    {"pdp_min_cm2": 50, "pdp_max_cm2": 100, "min_height_mm": 2},
    {"pdp_min_cm2": 100, "pdp_max_cm2": 500, "min_height_mm": 3},
    {"pdp_max_cm2": None, "pdp_min_cm2": 500, "min_height_mm": 4},
]

FONT_SIZE_RULE = {
    "rule_id": "R7_FONT",
    "rule_name": "Font Size Compliance",
    "rule_reference": "Rule 7 (Table I)",
    "description": (
        "The height of any numeral or letter used in mandatory declarations "
        "shall not be less than the minimum prescribed based on the area of "
        "the Principal Display Panel."
    ),
    "severity": "medium",
}

# ---------------------------------------------------------------------------
# Rule 8: Principal Display Panel
# ---------------------------------------------------------------------------
PDP_RULE = {
    "rule_id": "R8_PDP",
    "rule_name": "Declarations on Principal Display Panel",
    "rule_reference": "Rule 8",
    "description": (
        "All mandatory declarations must appear on the Principal Display "
        "Panel — the part of the package most likely to be displayed or "
        "examined under normal conditions of purchase."
    ),
    "severity": "medium",
}

# ---------------------------------------------------------------------------
# Additional checks
# ---------------------------------------------------------------------------
UNIT_SALE_PRICE_RULE = {
    "rule_id": "R6_UNIT",
    "rule_name": "Unit Sale Price (USP)",
    "rule_reference": "Rule 6(2) [2022 Amendment]",
    "description": (
        "The unit sale price (e.g. ₹/g, ₹/kg, ₹/ml, ₹/litre, ₹/piece) shall be "
        "declared on packages exceeding 1g or 1ml to enable direct consumer price comparison."
    ),
    "severity": "high",
}

LANGUAGE_RULE = {
    "rule_id": "R6_LANG",
    "rule_name": "Language of Declarations",
    "rule_reference": "Rule 6(3)",
    "description": (
        "Declarations shall be in English or Hindi (Devanagari script). "
        "Additional regional languages may also be used."
    ),
    "severity": "medium",
}

BARCODE_RULE = {
    "rule_id": "BARCODE",
    "rule_name": "Barcode / QR Code Presence",
    "rule_reference": "Best Practice / Industry Standard",
    "description": (
        "A valid barcode (EAN-13, UPC-A, etc.) or QR code should be "
        "present on the package for traceability."
    ),
    "severity": "low",
}

MRP_FORMAT_RULE = {
    "rule_id": "MRP_FMT",
    "rule_name": "MRP Format Compliance",
    "rule_reference": "Rule 6(1)(e)",
    "description": (
        "MRP must be expressed as 'MRP Rs. _____ (inclusive of all taxes)' "
        "or 'MRP ₹ _____ (incl. of all taxes)'."
    ),
    "severity": "high",
}

DATE_FORMAT_RULE = {
    "rule_id": "DATE_FMT",
    "rule_name": "Date Format Compliance",
    "rule_reference": "Rule 6(1)(d)",
    "description": (
        "The month and year of manufacture / packing / import should be "
        "in the format MM/YYYY or 'Month YYYY'."
    ),
    "severity": "medium",
}

# ---------------------------------------------------------------------------
# Medicine / Pharma — Specific Rules (Drugs Rules / DPCO)
# ---------------------------------------------------------------------------
DRUG_LICENSE_RULE = {
    "rule_id": "DRUG_LIC",
    "rule_name": "Drug Manufacturing License Number",
    "rule_reference": "Drugs & Cosmetics Rules",
    "description": (
        "The manufacturing license number (Mfg. Lic. No.) issued by the "
        "State Drug Controller must be declared on the package."
    ),
    "severity": "high",
}

COMPOSITION_RULE = {
    "rule_id": "COMP_1",
    "rule_name": "Composition / Formulation",
    "rule_reference": "Drugs & Cosmetics Rules",
    "description": (
        "The complete composition or formulation of the drug, including "
        "active ingredients and their quantities, must be declared."
    ),
    "severity": "high",
}

DOSAGE_RULE = {
    "rule_id": "DOSE_1",
    "rule_name": "Dosage Instructions",
    "rule_reference": "Drugs & Cosmetics Rules",
    "description": (
        "Dosage instructions or a directive such as 'As directed by the "
        "Physician' must be present on the drug packaging."
    ),
    "severity": "high",
}

WARNING_RULE = {
    "rule_id": "WARN_1",
    "rule_name": "Warning / Caution Statements",
    "rule_reference": "Drugs & Cosmetics Rules",
    "description": (
        "Appropriate warning and caution statements must be declared on "
        "the drug packaging, including usage precautions and contraindications."
    ),
    "severity": "medium",
}

SCHEDULE_RULE = {
    "rule_id": "SCHED_1",
    "rule_name": "Schedule Classification",
    "rule_reference": "Drugs & Cosmetics Rules",
    "description": (
        "If applicable, the drug's schedule classification (Schedule H, "
        "Schedule G, Schedule X, etc.) must be declared on the packaging."
    ),
    "severity": "medium",
}

MFG_LICENSE_RULE = {
    "rule_id": "MFG_LIC",
    "rule_name": "Manufacturing License Number",
    "rule_reference": "Best Practice / Industry Standard",
    "description": (
        "A manufacturing license number (Mfg. Lic. No.) should be present "
        "on the package for traceability and regulatory compliance."
    ),
    "severity": "medium",
}

# ---------------------------------------------------------------------------
# Rule Sets by Category
# ---------------------------------------------------------------------------
# Universal Core (Rule 6) - applies to all general commodities
UNIVERSAL_CORE_RULES: Dict[str, Dict] = {
    **MANDATORY_DECLARATIONS,
    FONT_SIZE_RULE["rule_id"]: FONT_SIZE_RULE,
    PDP_RULE["rule_id"]: PDP_RULE,
    UNIT_SALE_PRICE_RULE["rule_id"]: UNIT_SALE_PRICE_RULE,
    LANGUAGE_RULE["rule_id"]: LANGUAGE_RULE,
    BARCODE_RULE["rule_id"]: BARCODE_RULE,
    MRP_FORMAT_RULE["rule_id"]: MRP_FORMAT_RULE,
    DATE_FORMAT_RULE["rule_id"]: DATE_FORMAT_RULE,
}

# Medicines / Drugs - entirely different regime (DPCO / Drugs Rules)
# Excludes general MRP format, general date formats, etc.
MEDICINE_RULES: Dict[str, Dict] = {
    "R6_1_A_NAME": MANDATORY_DECLARATIONS["R6_1_A_NAME"],
    "R6_1_A_ADDR": MANDATORY_DECLARATIONS["R6_1_A_ADDR"],
    "R6_1_B": MANDATORY_DECLARATIONS["R6_1_B"],  # Common name
    "R6_1_C": MANDATORY_DECLARATIONS["R6_1_C"],  # Net Qty
    "R6_1_F": MANDATORY_DECLARATIONS["R6_1_F"],  # Consumer care
    "R6_1_G": MANDATORY_DECLARATIONS["R6_1_G"],  # Origin
    FONT_SIZE_RULE["rule_id"]: FONT_SIZE_RULE,
    PDP_RULE["rule_id"]: PDP_RULE,
    LANGUAGE_RULE["rule_id"]: LANGUAGE_RULE,
    BARCODE_RULE["rule_id"]: BARCODE_RULE,
    # Medicine-specific rules
    DRUG_LICENSE_RULE["rule_id"]: DRUG_LICENSE_RULE,
    COMPOSITION_RULE["rule_id"]: COMPOSITION_RULE,
    DOSAGE_RULE["rule_id"]: DOSAGE_RULE,
    WARNING_RULE["rule_id"]: WARNING_RULE,
    SCHEDULE_RULE["rule_id"]: SCHEDULE_RULE,
}

# Electronics / Hardware - No expiry dates
ELECTRONICS_RULES: Dict[str, Dict] = {
    k: v for k, v in UNIVERSAL_CORE_RULES.items() 
}

# Food & Goods - Universal + FSSAI rules
FOOD_RULES: Dict[str, Dict] = {
    k: v for k, v in UNIVERSAL_CORE_RULES.items()
}

# Cosmetics - Universal + INCI, Mfg Lic
COSMETICS_RULES: Dict[str, Dict] = {
    k: v for k, v in UNIVERSAL_CORE_RULES.items()
}

# Chemicals - Universal + Hazard
CHEMICAL_RULES: Dict[str, Dict] = {
    k: v for k, v in UNIVERSAL_CORE_RULES.items()
}

# Collect all rules for fallback/iteration
ALL_RULES: Dict[str, Dict] = {
    **UNIVERSAL_CORE_RULES,
    DRUG_LICENSE_RULE["rule_id"]: DRUG_LICENSE_RULE,
    COMPOSITION_RULE["rule_id"]: COMPOSITION_RULE,
    DOSAGE_RULE["rule_id"]: DOSAGE_RULE,
    WARNING_RULE["rule_id"]: WARNING_RULE,
    SCHEDULE_RULE["rule_id"]: SCHEDULE_RULE,
    MFG_LICENSE_RULE["rule_id"]: MFG_LICENSE_RULE,
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
VALID_QUANTITY_UNITS = {
    "g", "gm", "gms", "gram", "grams",
    "kg", "kgs", "kilogram", "kilograms",
    "mg", "milligram", "milligrams",
    "ml", "millilitre", "millilitres", "milliliter", "milliliters",
    "l", "ltr", "litre", "litres", "liter", "liters",
    "cm", "centimetre", "centimetres", "centimeter", "centimeters",
    "m", "metre", "metres", "meter", "meters",
    "mm", "millimetre", "millimetres", "millimeter", "millimeters",
    "sq cm", "sq m", "sq ft",
    "pcs", "pieces", "nos", "numbers", "units", "pairs",
    "capsules", "tablets", "sachets", "wipes",
}

# Regex patterns
MRP_PATTERN = re.compile(
    r"(?:MRP|M\.?\s*R\.?\s*P\.?)"
    r"[\s:.\-]*"
    r"(?:Rs\.?|₹|INR|Rupees?|R\b|R(?=[\s:.\-\d])|`|\?|\$)?\s*"
    r"[\s:.\-]*"
    r"[\d,]+(?:\.\d{1,2})?\s*"
    r"(?:\(?(?:incl(?:usive)?|inc)\.?\s*(?:of\s+)?all\s+taxes\)?)?",
    re.IGNORECASE,
)

DATE_PATTERN = re.compile(
    r"(?:"
    r"(?:0?[1-9]|1[0-2])[/\-.](?:20\d{2}|19\d{2})"  # MM/YYYY
    r"|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s*[,.]?\s*(?:20\d{2}|19\d{2})"  # Month YYYY
    r")",
    re.IGNORECASE,
)

NET_QUANTITY_PATTERN = re.compile(
    r"(?:net\s+(?:quantity|qty|wt|weight|content|vol|volume)\s*[:\-]?\s*)?"
    r"(\d+(?:\.\d+)?)\s*"
    r"(g|gm|gms|grams?|kg|kgs|kilograms?|mg|milligrams?"
    r"|ml|millilitres?|milliliters?|l|ltr|litres?|liters?"
    r"|cm|centimetres?|centimeters?|m|metres?|meters?"
    r"|mm|millimetres?|millimeters?"
    r"|pcs|pieces|nos|numbers|units|pairs"
    r"|capsules|tablets|sachets|wipes)",
    re.IGNORECASE,
)


def get_min_font_height(pdp_area_cm2: float) -> float:
    """Return the minimum required font height (mm) for a given PDP area (cm²)."""
    for entry in FONT_SIZE_TABLE:
        max_area = entry.get("pdp_max_cm2")
        if max_area is None or pdp_area_cm2 < max_area:
            return entry["min_height_mm"]
    return 4.0  # Default for large packages


def validate_mrp_format(mrp_text: str) -> Tuple[bool, str]:
    """Check if MRP text follows the prescribed format."""
    if not mrp_text:
        return False, "MRP not found on the package."
    if MRP_PATTERN.search(mrp_text):
        # Check for 'inclusive of all taxes' mention
        inclusive_pattern = re.compile(
            r"incl(?:usive)?\.?\s*(?:of\s+)?all\s+taxes", re.IGNORECASE
        )
        if inclusive_pattern.search(mrp_text):
            return True, f"MRP format is compliant: '{mrp_text}'"
        return False, (
            f"MRP found ('{mrp_text}') but missing 'inclusive of all taxes' declaration."
        )
    return False, (
        f"MRP declaration '{mrp_text}' does not follow the prescribed format: "
        "'MRP Rs. _____ (inclusive of all taxes)'"
    )


def validate_date_format(date_text: str) -> Tuple[bool, str]:
    """Check if date follows MM/YYYY or Month YYYY format."""
    if not date_text:
        return False, "Month and year of manufacture/packing/import not found."
    if DATE_PATTERN.search(date_text):
        return True, f"Date format is compliant: '{date_text}'"
    return False, (
        f"Date '{date_text}' does not follow prescribed format (MM/YYYY or Month YYYY)."
    )


def validate_net_quantity(quantity_text: str) -> Tuple[bool, str]:
    """Check if net quantity is declared with standard SI units."""
    if not quantity_text:
        return False, "Net quantity not found on the package."
    match = NET_QUANTITY_PATTERN.search(quantity_text)
    if match:
        value, unit = match.groups()
        return True, f"Net quantity is compliant: {value} {unit}"
    return False, (
        f"Net quantity '{quantity_text}' is not in standard SI units "
        "(g, kg, ml, L, cm, m, pieces, etc.)."
    )


# ---------------------------------------------------------------------------
# Statutory Penalties — Legal Metrology Act, 2009
# ---------------------------------------------------------------------------
STATUTORY_PENALTIES = {
    "SEC_36_1": {
        "section": "Section 36(1), Legal Metrology Act, 2009",
        "title": "Penalty for Non-Standard Packages & Missing Declarations",
        "statutory_text": (
            "Whoever manufactures, packs, imports, sells, distributes, delivers or "
            "otherwise transfers, offers, exposes or puts in condition for sale, or "
            "has in his possession for sale, any pre-packaged commodity which does not "
            "conform to the declarations on the package as prescribed under the "
            "Legal Metrology (Packaged Commodities) Rules, 2011, shall be punished."
        ),
        "first_offence": "Fine up to ₹25,000",
        "second_offence": "Fine up to ₹50,000",
        "subsequent_offence": "Fine up to ₹1,00,000 or imprisonment up to 1 year, or both",
        "compoundable": True,
    },
    "SEC_36_2": {
        "section": "Section 36(2), Legal Metrology Act, 2009",
        "title": "Penalty for Selling Above Maximum Retail Price (MRP)",
        "statutory_text": (
            "Whoever manufactures, packs or sells any non-standard package or "
            "charges in excess of the Maximum Retail Price (MRP) declared on the package "
            "shall be punished with fine or imprisonment."
        ),
        "first_offence": "Fine up to ₹25,000",
        "second_offence": "Fine up to ₹50,000",
        "subsequent_offence": "Fine up to ₹1,00,000 or imprisonment up to 1 year, or both",
        "compoundable": True,
    },
}

def get_statutory_penalty(rule_id: str) -> Optional[Dict]:
    """Return the statutory Legal Metrology Act penal section for a given rule violation."""
    if rule_id in ("R6_1_E", "MRP_FMT"):
        return STATUTORY_PENALTIES["SEC_36_2"]
    if rule_id.startswith("R6") or rule_id.startswith("R7") or rule_id.startswith("R8") or rule_id in ("BATCH_1", "BB_1", "DATE_FMT", "COO_1"):
        return STATUTORY_PENALTIES["SEC_36_1"]
    return None
