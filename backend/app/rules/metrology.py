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
    "rule_name": "Unit Sale Price",
    "rule_reference": "Rule 6(2)",
    "description": (
        "The unit sale price shall be declared to enable consumers to "
        "compare the price per standard unit."
    ),
    "severity": "low",
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

# Collect all rules for iteration
ALL_RULES: Dict[str, Dict] = {
    **MANDATORY_DECLARATIONS,
    FONT_SIZE_RULE["rule_id"]: FONT_SIZE_RULE,
    PDP_RULE["rule_id"]: PDP_RULE,
    UNIT_SALE_PRICE_RULE["rule_id"]: UNIT_SALE_PRICE_RULE,
    LANGUAGE_RULE["rule_id"]: LANGUAGE_RULE,
    BARCODE_RULE["rule_id"]: BARCODE_RULE,
    MRP_FORMAT_RULE["rule_id"]: MRP_FORMAT_RULE,
    DATE_FORMAT_RULE["rule_id"]: DATE_FORMAT_RULE,
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
    r"(?:MRP|M\.R\.P\.?)\s*(?:Rs\.?|₹|INR)\s*[\d,]+(?:\.\d{1,2})?\s*"
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
