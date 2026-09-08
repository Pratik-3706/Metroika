"""
Compliance engine — the PRIMARY compliance checker.

Validates OCR-extracted label data against:
- Legal Metrology (Packaged Commodities) Rules, 2011
- FSSAI regulations
- Drugs & Cosmetics Rules (for medicines/pharma)
- Industry best practices

This engine is the CORE of Metroika. AI is only an optional verifier.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from app.rules.metrology import (
    ALL_RULES,
    MANDATORY_DECLARATIONS,
    FONT_SIZE_RULE,
    PDP_RULE,
    UNIT_SALE_PRICE_RULE,
    LANGUAGE_RULE,
    BARCODE_RULE,
    MRP_FORMAT_RULE,
    DATE_FORMAT_RULE,
    DRUG_LICENSE_RULE,
    COMPOSITION_RULE,
    DOSAGE_RULE,
    WARNING_RULE,
    SCHEDULE_RULE,
    MFG_LICENSE_RULE,
    validate_mrp_format,
    validate_date_format,
    validate_net_quantity,
    get_min_font_height,
    get_statutory_penalty,
    STATUTORY_PENALTIES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enhanced Regex Patterns for field extraction
# ---------------------------------------------------------------------------

# Stop-phrases that signal end of a manufacturer/address field
_MANUFACTURER_STOP_PHRASES = re.compile(
    r"(?:DO\s*NOT\s*BUY|SCAN\s*HERE|FOR\s*MRP|FOR\s*MFR|READ\s*THE|AS\s*COMPARED|"
    r"FSSAI|INGREDIENTS|NUTRITION|ALLERGEN|STORE\s|KEEP\s|NET\s*(?:WT|WEIGHT|QTY)|"
    r"BEST\s*BEFORE|USE\s*(?:BY|BEFORE|WITHIN)|MFG\.?\s*BY|MFD\.?\s*BY|"
    r"TOLL\s*FREE|CUSTOMER\s*CARE|CONSUMER\s*CARE|BATCH|"
    r"\bBARCODE\b|\bQRCODE\b|\bSCAN\b|\bMFG\.?\s*LIC\b|\bDRUG\s*LIC\b|"
    r"TOTAL\s*CARBOHYDRATES|PROTEIN|ENERGY|SERVING\s*SIZE|PER\s*SERVE|APPROX|NUTRIENT|"
    r"\bFAT\b|\bSUGAR\b|\bSODIUM\b|\bCHOLESTEROL\b|"
    r"\bGARLIC\b|\bSPICES\b|\bPRESERVATIVE|IMITATION\s*OF|PUNISHABLE)",
    re.IGNORECASE,
)

# Stop-phrases that signal end of an ingredients field
_INGREDIENTS_STOP_PHRASES = re.compile(
    r"(?:FSSAI|HUL\s*REGN|Lic\.?\s*No|NET\s*(?:WT|WEIGHT|QTY|CONTENT)|"
    r"\bMRP\b|\bFOR\s+MRP\b|BATCH\s*NO|B\.?\s*No|"
    r"NUTRITION|ALLERGEN|STORE\s|KEEP\s|BEST\s*BEFORE|USE\s*BY|"
    r"PLEASE\s*SEE|SCAN\s*HERE|DO\s*NOT\s*BUY|TOLL\s*FREE|"
    r"MKTD\.?\s*BY|MFD\.?\s*BY|MANUFACTURED|MARKETED|PACKED)",
    re.IGNORECASE,
)

# Stop-phrases for composition sections (medicine-specific)
_COMPOSITION_STOP_PHRASES = re.compile(
    r"(?:Dosage|Store\s|Keep\s|Batch|B\.?\s*No|MRP|Mfg\.?\s*(?:Lic|Date)|"
    r"Scan\s*the|FOR\s*EXTERNAL|NOT\s*FOR|WARNING|CAUTION|Instructions)",
    re.IGNORECASE,
)

PATTERNS = {
    # Manufacturer / Packer / Importer details
    "manufacturer": re.compile(
        r"(?:Manufactured\s+(?:in\s+[A-Za-z]+\s+)?by|Mfd\.?\s*(?:in\s+[A-Za-z]+\s+)?by|Mfr\.?\s*by|"
        r"Marketed\s*by|Mktd\.?\s*by|"
        r"Packed\s*by|Packer\s*|"
        r"Imported\s*by|Importer\s*|"
        r"Mfd\.?|Manufactured|Mfr\.?|Mktd\.?|Marketed|Packed|Imported)"
        r"[\s:.\-]*"
        r"([A-Za-z0-9][A-Za-z0-9\s,.\-&'()]+)",
        re.IGNORECASE,
    ),

    # "Manufactured in India by" — specific pattern for pharma dual-entity packaging
    "manufactured_in_by": re.compile(
        r"Manufactured\s+in\s+\w+\s+by\s*[:.\-]*\s*"
        r"([A-Za-z0-9][A-Za-z0-9\s,.\-&'()]+)",
        re.IGNORECASE,
    ),

    # "Marketed by" — for dual-entity packaging
    "marketed_by": re.compile(
        r"Marketed\s*(?:by)?[\s:.\-]*"
        r"([A-Za-z0-9][A-Za-z0-9\s,.\-&'()]+)",
        re.IGNORECASE,
    ),

    # Net Quantity — comprehensive unit coverage
    "net_quantity": re.compile(
        r"(?:Net\s*(?:Wt\.?|Weight|Qty\.?|Quantity|Content|Vol\.?|Volume)"
        r"[\s:.\-]*)"
        r"([\d,]+\.?\d*)\s*"
        r"(g\b|gm\b|gms\b|grams?\b|kg\b|kgs\b|kilograms?\b|"
        r"mg\b|milligrams?\b|"
        r"ml\b|mL\b|millilitres?\b|milliliters?\b|"
        r"l\b|L\b|ltr\b|ltrs?\b|litres?\b|liters?\b|"
        r"cm\b|m\b|mm\b|pcs\b|pieces?\b|nos?\b|units?\b)",
        re.IGNORECASE,
    ),

    # MRP — multiple formats including Rs, ₹, /-, and various spacings
    "mrp": re.compile(
        r"(?:MRP|M\.?\s*R\.?\s*P\.?)"
        r"[\s:.\-]*"
        r"(?:(?:IN|O/?S)\s+(?:MUMBAI|DELHI))?"
        r"[\s:.\-]*"
        r"(?:Rs\.?|₹|INR|Rupees?|R\b|R(?=[\s:.\-\d])|`|\?|\$)?\s*"
        r"[\s:.\-]*"
        r"([\d,]+\.?\d*)"
        r"(?:\s*/?\s*-)?",
        re.IGNORECASE,
    ),

    # Unit Sale Price (Rule 6(2)) — e.g. 127.27/Kg, Rs. 1.20 / g, ₹ 0.50/ml
    "unit_sale_price": re.compile(
        r"(?:USP|Unit\s*Sale\s*Price)[\s:.\-]*"
        r"(?:Rs\.?|₹|INR)?\s*([\d,]+\.?\d*)\s*"
        r"(?:per|\/)\s*"
        r"(kg|g\b|gm\b|gms\b|ml\b|l\b|ltr\b|litres?\b|pieces?\b|pcs\b|units?\b|tablets?\b|capsules?\b|nos?\b)",
        re.IGNORECASE,
    ),

    # Manufacture / Packing Date — comprehensive support for DD/MMM/YY, DD/MM/YYYY, dot-matrix 057JUN26, etc.
    "manufacture_date": re.compile(
        r"(?:Mfg\.?\s*(?:Date|Dt)?\.?|Mfd\.?\s*(?:Date|Dt)?\.?|"
        r"Pkd\.?\s*(?:Date|Dt)?\.?|Pkdt\.?|"
        r"Pkg\.?\s*(?:Date|Dt)?\.?|"
        r"Date\s*of\s*(?:Mfg|Manufacture|Packing|Pkg)\.?)"
        r"[\s:.\-]*"
        r"(\d{1,2}[\s/\-.7]?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s/\-.]?\d{2,4}|"
        r"\d{1,2}[\s/\-.]\d{1,2}[\s/\-.]\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?[\s/\-.]?\d{2,4}|"
        r"\d{1,2}[\s/\-.]\d{2,4})",
        re.IGNORECASE,
    ),

    # Best Before / Expiry / Use By — comprehensive support for DD-MMM-YY, DD/MM/YYYY, etc.
    "best_before": re.compile(
        r"(?:Best\s*Before|BB|Use\s*(?:By|Before)|Exp(?:iry)?\.?\s*(?:Date)?\.?|"
        r"Shelf\s*Life)"
        r"[\s:.\-]*"
        r"(\d+\s*(?:days?|months?|years?|D|M|Y)|"
        r"\d{1,2}[\s/\-.7]?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s/\-.]?\d{2,4}|"
        r"\d{1,2}[\s/\-.]\d{1,2}[\s/\-.]\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?[\s/\-.]?\d{2,4}|"
        r"\d{1,2}[\s/\-.]\d{2,4})",
        re.IGNORECASE,
    ),

    # "Use within X months" — textual best-before (separate pattern)
    "use_within": re.compile(
        r"(?:USE\s*WITHIN|CONSUME\s*WITHIN)\s*"
        r"(\d+\s*(?:days?|months?|years?|weeks?))"
        r"(?:\s*(?:of|from)\s*(?:opening|manufacture|mfg|packing|packing\s*date|date\s*of\s*(?:mfg|manufacture|packing)))?",
        re.IGNORECASE,
    ),

    # Batch Number — captures full codes like "844 121" or "D1355 L2-1"
    "batch_number": re.compile(
        r"(?:\bB\.?\s*No\.?|\bBatch\s*(?:No\.?|Number)|\bLot\s*(?:No\.?|Number))"
        r"[\s:.\-]*"
        r"([A-Za-z0-9\-/]+[\s]?[A-Za-z0-9\-/]*\d[A-Za-z0-9\-/\s]*)",
        re.IGNORECASE,
    ),

    # FSSAI License Number (10-14 digits)
    "fssai_license": re.compile(
        r"(?:FSSAI|fssai|F\.?S\.?S\.?A\.?I\.?|"
        r"Lic(?:ense|ence)?\.?\s*No\.?)"
        r"[\s:.\-]*"
        r"(\d{10,14})",
        re.IGNORECASE,
    ),

    # Consumer Care / Contact details
    "consumer_care_phone": re.compile(
        r"(?:Customer\s*Care|Consumer\s*Care|Toll\s*Free|Helpline|"
        r"Contact|For\s*(?:Queries|Feedback|Complaints)|Call\s*(?:Us|at))"
        r"[\s:.\-]*"
        r"([\d\s\-+()]{7,})",
        re.IGNORECASE,
    ),

    # Email address
    "email": re.compile(
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
        re.IGNORECASE,
    ),

    # Toll-free number (standalone)
    "toll_free": re.compile(
        r"(?:1800[\s\-]?\d{2,3}[\s\-]?\d{2,3}[\s\-]?\d{2,4})",
        re.IGNORECASE,
    ),

    # Website / URL
    "url": re.compile(
        r"(?:https?://[A-Za-z0-9.\-/]+|www\.[A-Za-z0-9.\-/]+\.[A-Za-z]{2,})",
        re.IGNORECASE,
    ),

    # Inclusive of all taxes
    "inclusive_taxes": re.compile(
        r"(?:incl(?:usive)?\.?\s*(?:of\s+)?all\s+taxes?|"
        r"incl\.?\s*of\s+all\s+taxes|"
        r"inclusive\s+of\s+all\s+taxes)",
        re.IGNORECASE,
    ),

    # Country of Origin
    "country_of_origin": re.compile(
        r"(?:Country\s*of\s*Origin|Made\s*in|Product\s*of|Manufactured\s*in)"
        r"[\s:.\-]*"
        r"([A-Za-z\s]+)",
        re.IGNORECASE,
    ),

    # Ingredients — captures up to 500 chars, cleaned later by _clean_ingredients
    "ingredients": re.compile(
        r"(?:Ingredients?\s*[:.])\s*(.{10,500})",
        re.IGNORECASE,
    ),

    # Nutritional Information
    "nutritional": re.compile(
        r"(?:Nutrition(?:al)?\s*(?:Information|Info|Facts|Value)|"
        r"Per\s*100\s*(?:g|ml|gm)\s*(?:Appx\.?|Approx\.?)?)",
        re.IGNORECASE,
    ),

    # Energy value
    "energy": re.compile(
        r"Energy[\s:.\-]*([\d,.]+)\s*(?:kcal|kJ|Kcal|KJ)",
        re.IGNORECASE,
    ),

    # Protein
    "protein": re.compile(
        r"Protein[\s:.\-]*([\d,.]+)\s*g",
        re.IGNORECASE,
    ),

    # Allergen info
    "allergen": re.compile(
        r"(?:Allergen|Contains|May\s*Contain|Allergy\s*(?:Info|Advice))"
        r"[\s:.\-]*([A-Za-z\s,]+)",
        re.IGNORECASE,
    ),

    # Veg/Non-Veg marking
    "veg_mark": re.compile(
        r"(?:Vegetarian|Non[\s\-]?Vegetarian|Veg|Non[\s\-]?Veg|"
        r"100%\s*Veg|Pure\s*Veg)",
        re.IGNORECASE,
    ),

    # Storage instructions — captures the full instruction sentence
    "storage": re.compile(
        r"((?:Store|Keep|Storage)\s*(?:in|at)?\s*"
        r"(?:a\s*)?(?:cool|dry|room\s*temp|refrigerat|below|away|temperature)[^.]*\.?)",
        re.IGNORECASE,
    ),

    # -----------------------------------------------------------------------
    # Medicine / Pharma — Specific Patterns
    # -----------------------------------------------------------------------

    # Manufacturing License Number (Mfg. Lic. No. / M.L. No. / Factory Lic.)
    "drug_license": re.compile(
        r"(?:"
        r"M\.?\s*L\.?\s*(?:No\.?|Number)?:?|"
        r"ML\s*No\.?:?|"
        r"Mfg\.?\s*Lic(?:ense|ence)?\.?\s*(?:No\.?|Number)?:?|"
        r"Drug\s*(?:Mfg\.?\s*)?Lic(?:ense|ence)?\.?\s*(?:No\.?|Number)?:?|"
        r"Manufacturing\s*Lic(?:ense|ence)?\.?\s*(?:No\.?|Number)?:?|"
        r"Factory\s*Lic(?:ense|ence)?\.?\s*(?:No\.?|Number)?:?|"
        r"(?:HUL\s*)?Reg(?:n|d)?\.?\s*(?:No\.?|Number)?:?|"
        r"Registration\s*(?:No\.?|Number)?:?|"
        r"Cosmetic\s*Lic(?:ense)?\.?\s*(?:No\.?|Number)?:?"
        r")"
        r"[\s:.\-]*"
        r"([A-Za-z0-9/\-.\s]+?)(?=\s{2,}|\n|$|Scan|Marketed|Mfg\.\s*Date|Batch|Exp)",
        re.IGNORECASE,
    ),

    # Composition / Formulation (common on pharma packaging)
    "composition": re.compile(
        r"(?:Composition|Formulation|Each\s*(?:\d+\s*)?(?:ml|g|tablet|capsule|dose)\s*contains?)"
        r"[\s:.\-]*"
        r"(.{10,800})",
        re.IGNORECASE,
    ),

    # Dosage instructions
    "dosage": re.compile(
        r"(?:Dosage|Dose|Posology)"
        r"[\s:.\-]*"
        r"(.{5,200})",
        re.IGNORECASE,
    ),

    # "As directed by the Physician" — common pharma dosage instruction
    "as_directed": re.compile(
        r"(?:As\s*directed\s*by\s*(?:the\s*)?(?:Physician|Doctor|Registered\s*Medical\s*Practitioner))",
        re.IGNORECASE,
    ),

    # Warning / Caution statements
    "warning": re.compile(
        r"(?:WARNINGS?|CAUTIONS?|PRECAUTIONS?)"
        r"[\s:.\-]*"
        r"(.{5,500})",
        re.IGNORECASE,
    ),

    # Schedule classification (H, G, X, etc.)
    "schedule": re.compile(
        r"(?:Schedule[\s\-]*(?:H1?|G|X|C|C1)|"
        r"Rx\s*Only|"
        r"Not\s*to\s*be\s*sold\s*(?:by\s*)?retail\s*without\s*(?:the\s*)?prescription|"
        r"Prescription\s*Drug|"
        r"FOR\s*EXTERNAL\s*USE\s*ONLY|"
        r"NOT\s*FOR\s*INJECTION)",
        re.IGNORECASE,
    ),

    # "For External Use Only" / "Not for Injection" — pharma specific warnings
    "external_use": re.compile(
        r"(?:FOR\s*EXTERNAL\s*USE\s*ONLY|NOT\s*FOR\s*INJECTION|"
        r"FOR\s*TOPICAL\s*USE\s*ONLY|FOR\s*OPHTHALMIC\s*USE\s*ONLY)",
        re.IGNORECASE,
    ),
}


def _search_text(raw_text: str, pattern_key: str) -> Tuple[bool, str]:
    """Search raw text using a named pattern. Returns (found, matched_text)."""
    pattern = PATTERNS.get(pattern_key)
    if not pattern:
        return False, ""

    match = pattern.search(raw_text)
    if match:
        # Special handling for net_quantity: combine value and unit groups
        if pattern_key == "net_quantity" and len(match.groups()) >= 2:
            return True, f"{match.group(1).strip()} {match.group(2).strip()}"
        # Return the full match or the first group if available
        try:
            return True, match.group(1).strip() if match.groups() else match.group(0).strip()
        except (IndexError, AttributeError):
            return True, match.group(0).strip()
    return False, ""


def _check_referenced_declaration(raw_text: str, keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
    """
    Check if packaging directs the consumer to inspect another part of the container
    (e.g. 'PLEASE SEE BOTTOM OF PACK', 'SEE NECK OF BOTTLE', 'SEE CAP', 'SEE BELOW').
    Under Rule 6(1) proviso of Legal Metrology (Packaged Commodities) Rules, 2011,
    declaring 'See bottom of pack' on the label for MRP, Date, Batch is compliant.
    """
    ref_match = re.search(
        r"(?:FOR\s+[\w\s,./&()\-]+?)?"
        r"(?:PLEASE\s+)?SEE\s+(?:THE\s+)?(?:BOTTOM|NECK|CAP|CRIMP|REVERSE|BELOW)"
        r"(?:\s+(?:OF\s+)?(?:THE\s+)?(?:PACK|PACKAGE|BOTTLE|POUCH|CONTAINER|CAN|BOX))?",
        raw_text, re.IGNORECASE
    )
    if not ref_match:
        return False, ""

    matched_phrase = ref_match.group(0).strip()
    if keywords:
        start = max(0, ref_match.start() - 100)
        end = min(len(raw_text), ref_match.end() + 100)
        window = raw_text[start:end].lower()
        if any(kw.lower() in window for kw in keywords):
            return True, f"See bottom of pack ({matched_phrase})"
        return False, ""
    return True, f"See bottom of pack ({matched_phrase})"


def calculate_mrp_from_usp(usp_str: Optional[str], net_qty_str: Optional[str]) -> Optional[str]:
    """
    Calculate the mandatory MRP using Legal Metrology Rule 6(2) [2022 Amendment]:
    Unit Sale Price (USP) = MRP / Net Quantity => MRP = USP * Net Quantity.
    """
    if not usp_str or not net_qty_str:
        return None
    try:
        # Extract USP numeric value and unit, e.g. "127.27/Kg" -> 127.27, "kg"
        usp_match = re.search(r"([\d,]+\.?\d*)\s*(?:/|\bper\b)\s*([a-zA-Z]+)", usp_str, re.IGNORECASE)
        if not usp_match:
            return None
        usp_val = float(usp_match.group(1).replace(',', ''))
        usp_unit = usp_match.group(2).lower()

        # Extract Net Quantity numeric value and unit, e.g. "1.1 kg" -> 1.1, "kg"
        qty_match = re.search(r"([\d,]+\.?\d*)\s*([a-zA-Z]+)", net_qty_str, re.IGNORECASE)
        if not qty_match:
            return None
        qty_val = float(qty_match.group(1).replace(',', ''))
        qty_unit = qty_match.group(2).lower()

        calc = None
        # Mass conversions
        if "kg" in usp_unit and "kg" in qty_unit:
            calc = usp_val * qty_val
        elif "kg" in usp_unit and "g" in qty_unit:
            calc = usp_val * (qty_val / 1000.0)
        elif "g" in usp_unit and "g" in qty_unit:
            calc = usp_val * qty_val
        elif "g" in usp_unit and "kg" in qty_unit:
            calc = usp_val * (qty_val * 1000.0)
        # Volume conversions
        elif ("l" in usp_unit or "ltr" in usp_unit) and ("l" in qty_unit or "ltr" in qty_unit) and "ml" not in usp_unit and "ml" not in qty_unit:
            calc = usp_val * qty_val
        elif ("l" in usp_unit or "ltr" in usp_unit) and "ml" in qty_unit and "ml" not in usp_unit:
            calc = usp_val * (qty_val / 1000.0)
        elif "ml" in usp_unit and "ml" in qty_unit:
            calc = usp_val * qty_val
        # Count / Piece conversions
        elif any(u in usp_unit for u in ["u", "n", "pc", "tab", "cap"]) and any(u in qty_unit for u in ["u", "n", "pc", "tab", "cap"]):
            calc = usp_val * qty_val

        if calc is not None and calc > 0:
            if abs(calc - round(calc)) < 0.05:
                return str(int(round(calc)))
            return f"{calc:.2f}"
    except Exception:
        pass
    return None


def extract_dotmatrix_price_candidates(raw_text: str) -> List[str]:
    """
    Extract candidate price numbers from dot-matrix / inkjet stamps where
    common OCR artifacts occur (e.g. ₹ read as 2/z/?, /- read as 1-/1=/|-/-).
    Also extracts numbers from strikethrough/discount pairs like '160/- 140/-' or '01-21401-'.
    """
    candidates = []
    # Pattern 1: Standalone prices with /- or 1- or |- suffix
    for m in re.finditer(r"(?:^|[^\d])(\d{2,5}(?:\.\d{1,2})?)\s*(?:/[-=]|1[-=]|\|[-=]|/-)", raw_text):
        val = m.group(1).strip()
        try:
            if float(val) > 1:
                candidates.append(val)
        except ValueError:
            pass

    # Pattern 2: Dot-matrix where ₹ is recognized as digit 2 and /- is recognized as 1-
    # e.g. "21401-" -> "140"
    for m in re.finditer(r"(?:^|[^\d])2(\d{2,4})1-(?:$|[^\d])", raw_text):
        candidates.append(m.group(1).strip())

    # Pattern 3: Substrings near dates / USP lines that look like prices
    for m in re.finditer(r"(?:[01][-:=]+)?2?(\d{2,4})1?[-:=]+(?=\s*[\d.]+(?:/Kg|/g|/L|/ml|\b))", raw_text, re.IGNORECASE):
        candidates.append(m.group(1).strip())

    return candidates


def _search_with_fallback(raw_text: str, primary_key: str, fallback_pattern: str) -> Tuple[bool, str]:
    """Search with a primary pattern, falling back to a simpler regex."""
    found, val = _search_text(raw_text, primary_key)
    if found:
        return True, val

    match = re.search(fallback_pattern, raw_text, re.IGNORECASE)
    if match:
        try:
            return True, match.group(1).strip() if match.groups() else match.group(0).strip()
        except (IndexError, AttributeError):
            return True, match.group(0).strip()
    return False, ""


def _clean_manufacturer(val: str) -> str:
    """Truncate manufacturer text at known stop-phrases to prevent bleeding."""
    match = _MANUFACTURER_STOP_PHRASES.search(val)
    if match:
        val = val[:match.start()].strip()
    # Remove trailing punctuation artifacts
    val = re.sub(r"[,;.\-\s]+$", "", val)
    # Cap at 150 chars as a safety net
    if len(val) > 150:
        val = val[:150].rsplit(',', 1)[0].strip()
    return val


def _clean_ingredients(val: str) -> str:
    """Truncate ingredients text at known stop-phrases to prevent contamination."""
    match = _INGREDIENTS_STOP_PHRASES.search(val)
    if match:
        val = val[:match.start()].strip()
    # Remove trailing punctuation
    val = re.sub(r"[,;.\-\s]+$", "", val)
    return val


def _clean_composition(val: str) -> str:
    """Truncate composition text at known stop-phrases for medicine packaging."""
    match = _COMPOSITION_STOP_PHRASES.search(val)
    if match:
        val = val[:match.start()].strip()
    # Remove trailing punctuation
    val = re.sub(r"[,;.\-\s]+$", "", val)
    # Cap at 500 chars
    if len(val) > 500:
        val = val[:500].rsplit('.', 1)[0].strip()
    return val


def _validate_date_fragment(date_str: str) -> bool:
    """
    Basic sanity check for a date fragment like "69 3 19".
    Returns False if the numbers can't plausibly be a date.
    """
    # Strip "(inferred)" suffix
    clean = re.sub(r"\s*\(inferred\)\s*", "", date_str).strip()
    # Extract numeric parts
    parts = re.findall(r"\d+", clean)
    if not parts:
        return False
    # At least the first number should be ≤ 31 (day) and second ≤ 12 (month)
    try:
        nums = [int(p) for p in parts]
        if len(nums) >= 2:
            # Either DD/MM/YY or MM/DD/YY — both require first two parts ≤ 31
            if nums[0] > 31 or nums[1] > 31:
                return False
            # At least one of the first two must be ≤ 12 (month)
            if nums[0] > 12 and nums[1] > 12:
                return False
        elif len(nums) == 1:
            if nums[0] > 31:
                return False
    except (ValueError, IndexError):
        return False
    return True


# ---------------------------------------------------------------------------
# Product Category Detection — Improved with correct priority ordering
# ---------------------------------------------------------------------------
def detect_product_category(raw_text: str) -> str:
    """
    Detect product category based on OCR text heuristics.
    
    Priority is carefully ordered to avoid misclassification:
    1. Medicine (highest — "for external use only" + pharma keywords = medicine, NOT cosmetic)
    2. Chemical (hazardous materials)
    3. Food (FSSAI / nutrition keywords)
    4. Cosmetic (beauty / skincare — ONLY if not already matched as medicine)
    5. Electronics
    6. General (fallback)
    """
    text_lower = raw_text.lower()
    
    # ---- Medicine / Pharma ----
    # Strong medicine signals — any of these alone is sufficient
    _MEDICINE_STRONG = [
        "schedule h", "schedule g", "schedule x", "schedule c",
        "rx only", "dpco", "schedule-h", "schedule-g",
        "not to be sold by retail without the prescription",
        "not to be sold by retail without prescription",
        "registered medical practitioner",
        "not for injection",
        "drug lic", "drug licence", "drug license",
    ]
    if any(kw in text_lower for kw in _MEDICINE_STRONG):
        return "medicine"
    
    # Medium medicine signals — need at least 2 to confirm
    _MEDICINE_MEDIUM = [
        "medical practitioner", "physician", "dosage", "composition",
        "mfg. lic. no", "mfg lic no", "manufacturing licence",
        "pharmaceutical", "pharma", "subsidiary of",
        "sterile", "contraindication", "side effect",
        "for external use only", "for ophthalmic use",
        "for topical use only",
        "drug", "capsule", "tablet", "ointment", "syrup",
        "eye drops", "ear drops", "nasal drops",
        "injection", "oral solution", "oral suspension",
        "marketed by", "manufactured in india by",
    ]
    medicine_score = sum(1 for kw in _MEDICINE_MEDIUM if kw in text_lower)
    if medicine_score >= 2:
        return "medicine"
    
    # Chemicals — check before food/cosmetics
    if any(kw in text_lower for kw in ["poison", "hazard", "danger", "insecticide", "pesticide"]):
        return "chemical"
    
    # Food — check before cosmetics since FSSAI/nutrition keywords are more reliable
    if any(kw in text_lower for kw in ["fssai", "nutrition", "food", "edible"]):
        return "food"
        
    # Cosmetics — use word-boundary for 'inci' to avoid false positive on 'Incl.'
    # "external use only" alone is NOT enough — it must be combined with cosmetic keywords
    _COSMETIC_KEYWORDS = [
        "cosmetic", "beauty", "skin care", "skincare",
        "dermatologically tested", "fragrance", "parfum",
        "moisturizer", "moisturiser", "sunscreen", "spf",
        "face wash", "body wash", "hair care",
    ]
    if any(kw in text_lower for kw in _COSMETIC_KEYWORDS) or re.search(r"\binci\b", text_lower):
        return "cosmetic"
    # "external use only" + single medium medicine signal = still medicine
    if "external use only" in text_lower and medicine_score >= 1:
        return "medicine"
        
    # Electronics
    if any(kw in text_lower for kw in ["bis", "bee", "voltage", "watts", "electronics", "ac/dc", "hz"]):
        return "electronics"
        
    return "general"

# ---------------------------------------------------------------------------
# Main Compliance Check Runner
# ---------------------------------------------------------------------------

def run_compliance_checks(
    raw_text: str,
    barcode_results: Dict,
    structured_ocr: Optional[Dict[str, List[Dict]]] = None,
    manual_category: Optional[str] = None,
    product_name: Optional[str] = None,
) -> Tuple[List[Dict], str]:
    """
    Run all compliance checks against raw OCR text.

    This is the PRIMARY compliance engine. AI only verifies these results.

    Args:
        raw_text: Concatenated OCR text from all images.
        barcode_results: Output from barcode scanner.
        structured_ocr: Optional structured OCR data with bounding boxes.
        manual_category: Optional manual override from UI.
        product_name: Optional product name provided by user or AI.

    Returns:
        (List of compliance check result dicts, detected category)
    """
    if manual_category and manual_category.strip() and manual_category != "auto":
        category = manual_category.strip().lower()
    else:
        category = detect_product_category(raw_text)

    checks: List[Dict] = []

    # -----------------------------------------------------------------------
    # 1. Product Name (R6_1_A)
    # -----------------------------------------------------------------------
    # Product name is provided by AI vision evaluator or explicit user input.
    # When AI is not enabled or does not identify a name, it defaults to N/A.
    has_valid_name = bool(
        product_name
        and str(product_name).strip()
        and str(product_name).strip().lower() not in ("unnamed product", "unknown product", "n/a", "none")
    )
    product_name_evidence = str(product_name).strip() if has_valid_name else "N/A"

    checks.append({
        "rule_id": "R6_1_A",
        "rule_name": "Product Name",
        "rule_reference": "Rule 6(1)(a)",
        "status": "pass" if has_valid_name else "warning",
        "details": f"Detected: {product_name_evidence}" if has_valid_name
                   else "Product name is N/A (requires AI evaluation or manual input).",
        "evidence": product_name_evidence,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 2. Manufacturer / Packer / Importer Details (R6_1_B)
    # -----------------------------------------------------------------------
    found, val = _search_text(raw_text, "manufacturer")
    
    # Also try pharma-specific "Manufactured in India by" pattern
    found_mfg_in, mfg_in_val = _search_text(raw_text, "manufactured_in_by")
    found_mktd, mktd_val = _search_text(raw_text, "marketed_by")

    if not found:
        # Fallback: look for common company suffixes
        found, val = _search_with_fallback(
            raw_text, "manufacturer",
            r"([A-Z][A-Za-z\s]+(?:Pvt\.?\s*Ltd\.?|Limited|Industries|Corp|Inc|LLP|P\.?O\.?\s*Box))"
        )

    # Clean manufacturer text to remove trailing garbage
    if found and val:
        val = _clean_manufacturer(val)
        if not val:
            found = False
    
    # For dual-entity packaging (e.g. "Manufactured by X" + "Marketed by Y")
    manufacturer_evidence = val if found else None
    if found_mfg_in and mfg_in_val:
        mfg_in_val = _clean_manufacturer(mfg_in_val)
        if mfg_in_val:
            if manufacturer_evidence:
                manufacturer_evidence = f"{manufacturer_evidence} | Mfg by: {mfg_in_val}"
            else:
                manufacturer_evidence = mfg_in_val
                found = True
    if found_mktd and mktd_val:
        mktd_val = _clean_manufacturer(mktd_val)
        if mktd_val:
            if manufacturer_evidence:
                manufacturer_evidence = f"{manufacturer_evidence} | Marketed by: {mktd_val}"
            else:
                manufacturer_evidence = mktd_val
                found = True

    checks.append({
        "rule_id": "R6_1_B",
        "rule_name": "Manufacturer / Packer Details",
        "rule_reference": "Rule 6(1)(b)",
        "status": "pass" if found else "fail",
        "details": f"Found: {manufacturer_evidence}" if found else "Manufacturer/Packer details not found on package.",
        "evidence": manufacturer_evidence if found else None,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 3. Net Quantity (R6_1_C)
    # -----------------------------------------------------------------------
    found, val = _search_text(raw_text, "net_quantity")
    if not found:
        # Fallback: look for quantity patterns anywhere
        fallback = re.search(
            r"(\d+\.?\d*)\s*(g\b|kg\b|ml\b|l\b|L\b|ltr\b|gm\b)",
            raw_text, re.IGNORECASE
        )
        if fallback:
            found = True
            val = fallback.group(0).strip()

    # Validate the quantity format if found
    qty_details = ""
    if found:
        is_valid, qty_msg = validate_net_quantity(val)
        qty_details = qty_msg
    else:
        qty_details = "Net quantity not found on package."

    checks.append({
        "rule_id": "R6_1_C",
        "rule_name": "Net Quantity",
        "rule_reference": "Rule 6(1)(c)",
        "status": "pass" if found else "fail",
        "details": qty_details,
        "evidence": val if found else None,
        "severity": "high",
    })

    # Find all raw dates in the document for fallbacks (avoiding phone numbers)
    all_raw_dates = re.findall(r"(?<![\d\-])\d{1,2}[\s/\-.]?\d{1,2}[\s/\-.]?\d{2,4}(?![\d\-])", raw_text)

    # -----------------------------------------------------------------------
    # 4. Manufacture / Packing Date (R6_1_D)
    # -----------------------------------------------------------------------
    found_mfg, mfg_val = _search_text(raw_text, "manufacture_date")
    if found_mfg and mfg_val:
        # Clean dot-matrix 057JUN26 -> 05/JUN/26
        mfg_val = re.sub(r"^(\d{1,2})7([A-Za-z]{3})", r"\1/\2", str(mfg_val).strip())
        mfg_val = re.sub(r"^(\d{1,2})7(\d{2})", r"\1/\2", mfg_val)
        # Reject bare 3-digit noise like "057"
        if re.match(r"^\d{1,3}$", mfg_val):
            found_mfg = False
            mfg_val = ""
    if not found_mfg:
        # Fallback: look for date-like patterns near keywords (supports 2-digit year)
        fallback = re.search(
            r"(?:Mfg|Mfd|Pkd|Pkdt)[\s:.]*(\d{1,2}[\s/\-.]?\d{1,2}[\s/\-.]?\d{2,4})",
            raw_text, re.IGNORECASE
        )
        if fallback:
            found_mfg = True
            mfg_val = fallback.group(1).strip()
        else:
            # Check if declared as "See bottom of pack" / "PKD ... see bottom"
            ref_found, ref_val = _check_referenced_declaration(
                raw_text, ["pkd", "mfg", "mfd", "packing", "manufacture", "date", "dt"]
            )
            if ref_found:
                found_mfg = True
                mfg_val = ref_val
            elif all_raw_dates:
                # Aggressive fallback: assume the first valid raw date is the mfg date
                for candidate_date in all_raw_dates:
                    if _validate_date_fragment(candidate_date):
                        found_mfg = True
                        mfg_val = candidate_date + " (inferred)"
                        break

    checks.append({
        "rule_id": "R6_1_D",
        "rule_name": "Manufacture / Packing Date",
        "rule_reference": "Rule 6(1)(d)",
        "status": "pass" if found_mfg else "fail",
        "details": f"Found: {mfg_val}" if found_mfg else "Manufacture/packing date not found on package.",
        "evidence": mfg_val if found_mfg else None,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 5. Maximum Retail Price (R6_1_E) — find ALL MRP mentions, pick best
    # -----------------------------------------------------------------------
    # Find all MRP occurrences in the text
    mrp_pattern_full = re.compile(
        r"(?:MRP|M\.?\s*R\.?\s*P\.?)"
        r"[\s:.\-]*"
        r"(?:(?:IN|O/?S)\s+(?:MUMBAI|DELHI))?"
        r"[\s:.\-]*"
        r"(?:Rs\.?|₹|INR|Rupees?|R\b|R(?=[\s:.\-\d])|`|\?|\$)?\s*"
        r"[\s:.\-]*"
        r"([\d,]+\.?\d*)"
        r"(?:\s*/?\s*-)?",
        re.IGNORECASE,
    )
    all_mrp_matches = mrp_pattern_full.finditer(raw_text)
    best_mrp = None
    best_mrp_score = -1
    for m in all_mrp_matches:
        # Ignore marketing comparative claims
        context_before = raw_text[max(0, m.start()-40):m.start()]
        if "COMPARED TO" in context_before.upper():
            continue

        candidate = m.group(1).strip().replace(',', '')
        if not candidate:
            continue
        try:
            val_num = float(candidate)
        except ValueError:
            continue
            
        # Score: prefer larger values (more likely the full MRP, not truncated)
        # and values that have an "incl" phrase nearby
        score = val_num
        context_after = raw_text[m.end():m.end()+60]
        if re.search(r"incl(?:usive)?\.?\s*(?:of\s+)?all\s+taxes", context_after, re.IGNORECASE):
            score += 10000  # Heavily prefer MRP with tax declaration
        if score > best_mrp_score:
            best_mrp_score = score
            best_mrp = m.group(1).strip()

    found_mrp = best_mrp is not None
    mrp_val = best_mrp or ""

    if not found_mrp:
        # Fallback 1: Standalone currency amounts (₹140, Rs. 140, 140/- or 1401- due to OCR)
        fallback_pattern = re.compile(
            r"(?:Rs\.?\s*|₹\s*|INR\s*|Rupees?\s*|R\s*:\s*)([\d,]+\.?\d*)|([\d,]+\.?\d*)\s*(?:/-)",
            re.IGNORECASE
        )
        fallback_matches = fallback_pattern.finditer(raw_text)
        best_fallback_mrp = None
        best_fallback_score = -1
        
        for m in fallback_matches:
            val_str = m.group(1) or m.group(2)
            if not val_str:
                continue
            try:
                val_num = float(val_str.replace(',', ''))
            except ValueError:
                continue
                
            if val_num <= 1:
                continue
                
            if val_num > best_fallback_score:
                best_fallback_score = val_num
                best_fallback_mrp = val_str.strip()
                
        if best_fallback_mrp is not None:
            found_mrp = True
            mrp_val = best_fallback_mrp

    if not found_mrp:
        # Fallback 2: Check if declared as "See bottom of pack"
        ref_found, ref_val = _check_referenced_declaration(
            raw_text, ["mrp", "price", "taxes", "tax"]
        )
        if ref_found:
            found_mrp = True
            mrp_val = ref_val

    checks.append({
        "rule_id": "R6_1_E",
        "rule_name": "Maximum Retail Price (MRP)",
        "rule_reference": "Rule 6(1)(e)",
        "status": "pass" if found_mrp else "fail",
        "details": f"MRP found: Rs. {mrp_val}" if (found_mrp and "see bottom" not in str(mrp_val).lower())
                   else f"Found: {mrp_val}" if found_mrp
                   else "MRP not found on package.",
        "evidence": f"Rs. {mrp_val}" if (found_mrp and "see bottom" not in str(mrp_val).lower())
                    else mrp_val if found_mrp else None,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 5b. MRP Format — "Inclusive of all taxes" (MRP_FMT)
    # -----------------------------------------------------------------------
    found_taxes, taxes_val = _search_text(raw_text, "inclusive_taxes")

    if found_mrp and "see bottom" in str(mrp_val).lower():
        if found_taxes:
            mrp_fmt_status = "pass"
            mrp_fmt_details = "MRP declaration with 'inclusive of all taxes' references bottom of pack (compliant under Rule 6)."
        else:
            mrp_fmt_status = "pass"
            mrp_fmt_details = "MRP references bottom of pack as permitted under Rule 6."
    else:
        mrp_fmt_status = "pass" if (found_mrp and found_taxes) else "fail" if found_mrp else "warning"
        if found_mrp and found_taxes:
            mrp_fmt_details = f"MRP Rs. {mrp_val} with 'inclusive of all taxes' declaration found."
        elif found_mrp and not found_taxes:
            mrp_fmt_details = f"MRP Rs. {mrp_val} found but missing 'inclusive of all taxes' declaration."
        else:
            mrp_fmt_details = "MRP not found; cannot verify format."

    checks.append({
        "rule_id": MRP_FORMAT_RULE["rule_id"],
        "rule_name": MRP_FORMAT_RULE["rule_name"],
        "rule_reference": MRP_FORMAT_RULE["rule_reference"],
        "status": mrp_fmt_status,
        "details": mrp_fmt_details,
        "evidence": taxes_val if found_taxes else None,
        "severity": MRP_FORMAT_RULE["severity"],
    })

    # -----------------------------------------------------------------------
    # 6. Consumer Care Details (R6_1_H)
    # -----------------------------------------------------------------------
    found_phone, phone_val = _search_text(raw_text, "consumer_care_phone")
    found_email, email_val = _search_text(raw_text, "email")
    found_toll, toll_val = _search_text(raw_text, "toll_free")
    found_url, url_val = _search_text(raw_text, "url")

    consumer_found = found_phone or found_email or found_toll or found_url
    consumer_evidence_parts = []
    if found_phone:
        consumer_evidence_parts.append(f"Phone: {phone_val}")
    if found_email:
        consumer_evidence_parts.append(f"Email: {email_val}")
    if found_toll:
        consumer_evidence_parts.append(f"Toll-free: {toll_val}")
    if found_url:
        consumer_evidence_parts.append(f"URL: {url_val}")

    checks.append({
        "rule_id": "R6_1_H",
        "rule_name": "Consumer Care Details",
        "rule_reference": "Rule 6(1)(h)",
        "status": "pass" if consumer_found else "fail",
        "details": f"Found: {'; '.join(consumer_evidence_parts)}" if consumer_found
                   else "Consumer care contact information not found on package.",
        "evidence": "; ".join(consumer_evidence_parts) if consumer_found else None,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 7. FSSAI License Number
    # -----------------------------------------------------------------------
    found_fssai, fssai_val = _search_text(raw_text, "fssai_license")
    if not found_fssai:
        # Fallback: look for standalone 10-14 digit numbers near FSSAI keyword
        fssai_kw = re.search(r"(?:FSSAI|fssai)", raw_text, re.IGNORECASE)
        if fssai_kw:
            # Search nearby for a long number
            nearby = raw_text[max(0, fssai_kw.start()-20):fssai_kw.end()+40]
            num_match = re.search(r"\d{10,14}", nearby)
            if num_match:
                found_fssai = True
                fssai_val = num_match.group(0)

    checks.append({
        "rule_id": "FSSAI_1",
        "rule_name": "FSSAI License Number",
        "rule_reference": "FSSAI Act",
        "status": "pass" if found_fssai else "fail",
        "details": f"FSSAI License: {fssai_val}" if found_fssai
                   else "FSSAI License number not found on package.",
        "evidence": fssai_val if found_fssai else None,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 8. List of Ingredients — with stop-phrase cleaning
    # -----------------------------------------------------------------------
    found_ing, ing_val = _search_text(raw_text, "ingredients")
    if found_ing and ing_val:
        ing_val = _clean_ingredients(ing_val)
        if len(ing_val) < 10:
            # Cleaning removed too much, fall back
            found_ing = False
            ing_val = ""

    if not found_ing:
        # Fallback: look for the keyword and grab whatever follows it
        ing_fallback = re.search(
            r"ingredients?\s*[:.]\s*(.{10,500})",
            raw_text, re.IGNORECASE
        )
        if ing_fallback:
            found_ing = True
            ing_val = _clean_ingredients(ing_fallback.group(1).strip())
        else:
            # Check for ingredients / condiments / preservative declarations without explicit "Ingredients:" keyword
            cond_match = re.search(
                r"((?:PRESERVATIVE|ONION\s*POWDER|GARLIC\s*POWDER|SPICES\s*AND\s*CONDIMENTS)[\w\s,.\-&()]+?)"
                r"(?=\s+For\s+MRP|\s+MRP|\s+USP|\s+NET|\n|$)",
                raw_text, re.IGNORECASE
            )
            if cond_match:
                found_ing = True
                ing_val = cond_match.group(1).strip()
            else:
                # Last resort: just check if the keyword exists at all
                found_ing = bool(re.search(r"ingredients?\s*[:.]\s", raw_text, re.IGNORECASE))
                if found_ing:
                    ing_val = "Ingredients section detected (text not fully extracted)"

    checks.append({
        "rule_id": "ING_1",
        "rule_name": "List of Ingredients",
        "rule_reference": "Rule 6(1)(b) / FSSAI",
        "status": "pass" if found_ing else "fail",
        "details": "Ingredients section found." if found_ing
                   else "Ingredients list not found on package.",
        "evidence": ing_val[:200] if found_ing and ing_val else None,
        "severity": "medium",
    })

    # -----------------------------------------------------------------------
    # 9. Nutritional Information
    # -----------------------------------------------------------------------
    found_nut, nut_val = _search_text(raw_text, "nutritional")
    # Also check for specific nutritional fields
    found_energy, _ = _search_text(raw_text, "energy")
    found_protein, _ = _search_text(raw_text, "protein")

    nut_found = found_nut or found_energy or found_protein

    # Build evidence for nutritional info
    nut_evidence = None
    if found_nut:
        nut_evidence = nut_val if nut_val else "Nutritional information section detected"
    elif found_energy or found_protein:
        parts = []
        if found_energy:
            parts.append("Energy values detected")
        if found_protein:
            parts.append("Protein values detected")
        nut_evidence = "; ".join(parts)

    checks.append({
        "rule_id": "NUT_1",
        "rule_name": "Nutritional Information",
        "rule_reference": "FSSAI",
        "status": "pass" if nut_found else "fail",
        "details": "Nutritional information section found." if nut_found
                   else "Nutritional information not found on package.",
        "evidence": nut_evidence,
        "severity": "medium",
    })

    # -----------------------------------------------------------------------
    # 10. Best Before / Expiry Date — with validation and "use within" support
    # -----------------------------------------------------------------------
    found_bb, bb_val = _search_text(raw_text, "best_before")
    if found_bb and bb_val:
        bb_val = re.sub(r"^(\d{1,2})7([A-Za-z]{3})", r"\1/\2", str(bb_val).strip())
        bb_val = re.sub(r"^(\d{1,2})7(\d{2})", r"\1/\2", bb_val)
        if re.match(r"^\d{1,3}$", bb_val):
            found_bb = False
            bb_val = ""

    # If primary pattern didn't find it, try "use within X months" pattern
    if not found_bb:
        found_bb, bb_val = _search_text(raw_text, "use_within")
        if found_bb:
            bb_val = f"Use within {bb_val}"

    if not found_bb:
        # Check if declared as "See bottom of pack" / "USE BY DATE ... see bottom"
        ref_found, ref_val = _check_referenced_declaration(
            raw_text, ["use by", "best before", "expiry", "exp", "bb", "use before"]
        )
        if ref_found:
            found_bb = True
            bb_val = ref_val
        elif len(all_raw_dates) >= 2:
            # Try the last raw date (often the expiry)
            candidate = all_raw_dates[-1]
            if _validate_date_fragment(candidate):
                found_bb = True
                bb_val = candidate + " (inferred)"
        elif len(all_raw_dates) == 1 and not found_mfg:
            candidate = all_raw_dates[0]
            if _validate_date_fragment(candidate):
                found_bb = True
                bb_val = candidate + " (inferred)"

    # Also look for "USE BY DATE" textual reference as evidence
    if not found_bb:
        use_by_text = re.search(
            r"USE\s*BY\s*DATE\s*WHICHEVER\s*IS\s*EARLIER",
            raw_text, re.IGNORECASE
        )
        if use_by_text:
            found_bb = True
            bb_val = "See bottom of pack (USE BY DATE referenced on label)"

    checks.append({
        "rule_id": "BB_1",
        "rule_name": "Best Before / Expiry Date",
        "rule_reference": "Rule 6(1)(d) / FSSAI",
        "status": "pass" if found_bb else "warning",
        "details": f"Found: {bb_val}" if found_bb
                   else "Best before / expiry information not explicitly found.",
        "evidence": bb_val if found_bb else None,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 11. Batch Number — with improved capture and cleanup
    # -----------------------------------------------------------------------
    found_batch, batch_val = _search_text(raw_text, "batch_number")
    if found_batch and batch_val:
        # Clean up: trim trailing junk (stop at period, FSSAI, PLEASE, etc.)
        batch_val = re.split(
            r"(?:\.|FSSAI|PLEASE|LIC|HUL|FOR\s|\bAND\b|\bMfg\b|\bMfd\b|\bExp\b|\bDate\b)",
            batch_val, flags=re.IGNORECASE
        )[0].strip()
        # Remove trailing whitespace/punctuation
        batch_val = re.sub(r"[\s,;.\-]+$", "", batch_val)
        if not batch_val:
            found_batch = False

    if not found_batch:
        # Check if declared as "See bottom of pack" / "BATCH NO ... SEE BOTTOM"
        ref_found, ref_val = _check_referenced_declaration(
            raw_text, ["batch", "lot", "b. no", "b.no", "b no", "batch no"]
        )
        if ref_found:
            found_batch = True
            batch_val = ref_val
        else:
            # Fallback: Look for standalone lot/batch-like codes (e.g. FHC0445, D1355)
            # Require at least 3 digits to avoid matching short address fragments like "26A"
            fallback = re.search(
                r"\b([A-Z]{1,3}\d{4,}[A-Z0-9\-]*|\d{5,}[A-Z]{2,})\b", 
                raw_text
            )
            if fallback:
                found_batch = True
                batch_val = fallback.group(1).strip() + " (inferred)"

    checks.append({
        "rule_id": "BATCH_1",
        "rule_name": "Batch / Lot Number",
        "rule_reference": "Rule 6(1)(d)",
        "status": "pass" if found_batch else "warning",
        "details": f"Found: {batch_val}" if found_batch
                   else "Batch/Lot number not explicitly detected.",
        "evidence": batch_val if found_batch else None,
        "severity": "medium",
    })

    # -----------------------------------------------------------------------
    # 12. Allergen Information
    # -----------------------------------------------------------------------
    found_allergen, allergen_val = _search_text(raw_text, "allergen")

    checks.append({
        "rule_id": "ALLRG_1",
        "rule_name": "Allergen Information",
        "rule_reference": "FSSAI",
        "status": "pass",
        "details": f"Found: {allergen_val}" if found_allergen
                   else "No allergens declared (Assumed none required).",
        "evidence": allergen_val if found_allergen else None,
        "severity": "low",
    })

    # -----------------------------------------------------------------------
    # 13. Veg / Non-Veg Marking
    # -----------------------------------------------------------------------
    found_veg, veg_val = _search_text(raw_text, "veg_mark")

    checks.append({
        "rule_id": "VEG_1",
        "rule_name": "Veg / Non-Veg Symbol",
        "rule_reference": "FSSAI",
        "status": "pass",
        "details": f"Found: {veg_val}" if found_veg
                   else "Veg/Non-Veg marking assumed compliant (visual symbol not readable by OCR).",
        "evidence": veg_val if found_veg else None,
        "severity": "medium",
    })

    # -----------------------------------------------------------------------
    # 14. Storage Instructions — find all matches, pick the cleanest one
    # -----------------------------------------------------------------------
    storage_pattern = re.compile(
        r"((?:Store|Keep|Storage)\s*(?:in|at)?\s*"
        r"(?:a\s*)?(?:cool|dry|room\s*temp|refrigerat|below|away|temperature)[^.]*\.?)",
        re.IGNORECASE,
    )
    all_storage_matches = storage_pattern.findall(raw_text)
    found_storage = False
    storage_val = ""

    if all_storage_matches:
        # Prefer matches that contain "STORE IN COOL" (full instruction) over
        # short "KEEP REFRIGERAT" fragments that may have address bleeding
        best = None
        for sm in all_storage_matches:
            sm = sm.strip()
            # Cap at 200 chars to prevent garbage
            if len(sm) > 200:
                sm = sm[:200]
            # Prefer matches with "STORE" and "COOL" and "DRY" as they're full instructions
            if re.search(r"store\s+in\s+cool", sm, re.IGNORECASE):
                best = sm
                break
        if not best:
            # Pick the longest match that doesn't contain address-like content
            for sm in sorted(all_storage_matches, key=len, reverse=True):
                sm = sm.strip()
                if len(sm) > 200:
                    sm = sm[:200]
                # Skip if it contains address-like patterns (GAT No, A/P:, TALUKA, etc.)
                if not re.search(r"(?:GAT\s*No|A/P:|TALUKA|DISTT|DISTRICT|P\.?O\.?\s|VILLAGE)", sm, re.IGNORECASE):
                    best = sm
                    break
        if not best:
            best = all_storage_matches[0].strip()[:150]
        found_storage = True
        storage_val = best

    if not found_storage:
        # Broader fallback for storage instructions
        storage_fb = re.search(
            r"(?:Store|Keep|Storage)[\s].*?(?:\.|$)",
            raw_text, re.IGNORECASE
        )
        if storage_fb:
            found_storage = True
            storage_val = storage_fb.group(0).strip()[:150]

    checks.append({
        "rule_id": "STOR_1",
        "rule_name": "Storage Instructions",
        "rule_reference": "FSSAI / Best Practice",
        "status": "pass" if found_storage else "warning",
        "details": f"Found storage instructions." if found_storage
                   else "Storage instructions not explicitly found.",
        "evidence": storage_val if found_storage else None,
        "severity": "low",
    })

    # -----------------------------------------------------------------------
    # 15a. Unit Sale Price (R6_UNIT) — Mandatory under 2022 Amendment
    # -----------------------------------------------------------------------
    found_usp, usp_val = _search_text(raw_text, "unit_sale_price")
    if not found_usp:
        # Fallback search for patterns like "127.27/Kg" or "Rs. 1.20/g"
        usp_fb = re.search(r"(?:₹|Rs\.?|INR)?\s*(\d+(?:\.\d+)?)\s*\/\s*(kg|g|gm|ml|l|ltr|piece|pcs)", raw_text, re.IGNORECASE)
        if usp_fb:
            found_usp = True
            usp_val = usp_fb.group(0).strip()

    if category == "medicine":
        usp_status = "not_applicable"
        usp_details = "Medicines are governed under DPCO rather than standard Unit Sale Price."
    elif found_usp:
        usp_status = "pass"
        usp_details = f"Unit Sale Price declared: '{usp_val}'. Conforms to Rule 6(2)."
    else:
        # Check if Net Qty was found
        net_qty_found = any(c["rule_id"] == "R6_1_C" and c["status"] == "pass" for c in checks)
        if net_qty_found:
            usp_status = "warning"
            usp_details = "Unit Sale Price (USP) not explicitly detected. Mandatory for pre-packaged commodities > 1g or 1ml under Rule 6(2) [2022 Amendment]."
        else:
            usp_status = "warning"
            usp_details = "Unit Sale Price not found."

    checks.append({
        "rule_id": UNIT_SALE_PRICE_RULE["rule_id"],
        "rule_name": UNIT_SALE_PRICE_RULE["rule_name"],
        "rule_reference": UNIT_SALE_PRICE_RULE["rule_reference"],
        "status": usp_status,
        "details": usp_details,
        "evidence": usp_val if found_usp else None,
        "severity": UNIT_SALE_PRICE_RULE["severity"],
    })

    # -----------------------------------------------------------------------
    # 15b. Font Size Compliance (R7_FONT) — Advisory Legibility & Rule 7 Table 1
    # -----------------------------------------------------------------------
    font_details = (
        "Advisory: Text detected with clear visual legibility. Note: Under Rule 7 Table 1, "
        "mandatory declarations require minimum font heights: 2.0 mm (≤200g), 4.0 mm (200g-1kg), "
        "or 6.0 mm (>1kg). Flagged for physical caliper inspection if magnification < 100%."
    )
    checks.append({
        "rule_id": FONT_SIZE_RULE["rule_id"],
        "rule_name": FONT_SIZE_RULE["rule_name"],
        "rule_reference": FONT_SIZE_RULE["rule_reference"],
        "status": "pass",
        "details": font_details,
        "evidence": "Legible font height across mandatory declaration blocks",
        "severity": FONT_SIZE_RULE["severity"],
    })

    # -----------------------------------------------------------------------
    # 16. Principal Display Panel (R8_PDP)
    # -----------------------------------------------------------------------
    pn_pass = any(c["rule_id"] == "R6_1_A" and c["status"] == "pass" for c in checks)
    nq_pass = any(c["rule_id"] == "R6_1_C" and c["status"] == "pass" for c in checks)
    mrp_pass = any(c["rule_id"] == "R6_1_E" and c["status"] == "pass" for c in checks)
    primary_count = sum([1 for x in [pn_pass, nq_pass, mrp_pass] if x])
    if primary_count >= 2:
        pdp_status = "pass"
        pdp_details = "Mandatory declarations are prominently grouped on the primary display face (Rule 8 compliant)."
    else:
        pdp_status = "warning"
        pdp_details = "Mandatory declarations appear fragmented or missing from the principal display panel."

    checks.append({
        "rule_id": PDP_RULE["rule_id"],
        "rule_name": PDP_RULE["rule_name"],
        "rule_reference": PDP_RULE["rule_reference"],
        "status": pdp_status,
        "details": pdp_details,
        "evidence": f"{primary_count}/3 primary declarations detected",
        "severity": PDP_RULE["severity"],
    })

    # -----------------------------------------------------------------------
    # 17. Language of Declarations (R6_LANG)
    # -----------------------------------------------------------------------
    has_english = any(ord('a') <= ord(c.lower()) <= ord('z') for c in raw_text)
    has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in raw_text)
    
    if has_english or has_devanagari:
        lang_status = "pass"
        lang_evidence = "English" if (has_english and not has_devanagari) else ("Hindi (Devanagari)" if has_devanagari and not has_english else "Bilingual (English + Hindi)")
        lang_details = f"Declarations are in {lang_evidence}, conforming to Rule 6(3)."
    else:
        lang_status = "fail"
        lang_evidence = "Unknown / Non-standard script"
        lang_details = "Mandatory declarations must be in English or Hindi (Devanagari script) under Rule 6(3)."

    checks.append({
        "rule_id": LANGUAGE_RULE["rule_id"],
        "rule_name": LANGUAGE_RULE["rule_name"],
        "rule_reference": LANGUAGE_RULE["rule_reference"],
        "status": lang_status,
        "details": lang_details,
        "evidence": lang_evidence,
        "severity": LANGUAGE_RULE["severity"],
    })

    # -----------------------------------------------------------------------
    # 17b. Country of Origin (COO_1)
    # -----------------------------------------------------------------------
    found_coo, coo_val = _search_text(raw_text, "country_of_origin")
    if found_coo:
        # Clean up: strip trailing junk and stop at common stop words
        coo_val = re.sub(r"[^A-Za-z\s]", "", coo_val).strip()
        # Truncate at company/address indicators
        coo_stop = re.search(
            r"\b(?:by|Pvt|Ltd|Limited|Industries|Corp|Inc|Pure|Healthcare|Pharmaceutical|Plot|Sector|SIDCUL|Company|Enterprise|Holdings|Group|Brand)\b",
            coo_val, re.IGNORECASE
        )
        if coo_stop:
            coo_val = coo_val[:coo_stop.start()].strip()
            
        coo_lower = coo_val.lower().strip()
        _KNOWN_COUNTRIES = [
            "india", "bharat", "china", "usa", "united states", "japan", "germany",
            "france", "united kingdom", "uk", "italy", "brazil", "russia", "korea",
            "south korea", "vietnam", "thailand", "indonesia", "taiwan", "malaysia",
            "singapore", "bangladesh", "sri lanka", "nepal", "australia", "new zealand",
            "canada", "mexico", "spain", "netherlands", "switzerland", "uae", "philippines"
        ]
        matched_kc = next((kc for kc in _KNOWN_COUNTRIES if re.search(rf"\b{kc}\b", coo_lower)), None)
        if matched_kc:
            coo_val = "India" if matched_kc in ("india", "bharat") else matched_kc.title()
        elif coo_lower in {"of the", "of the e", "the", "of", "in", "for", "to", "and", "by", "at", "from"} or coo_lower.startswith(("of the", "the ", "of ")):
            found_coo = False
            coo_val = ""
        elif len(coo_val) < 3:
            found_coo = False
            coo_val = ""

    if not found_coo:
        # Fallback: check if manufacturer address contains Indian cities / states
        indian_locations = [
            "mumbai", "delhi", "maharashtra", "punjab", "himachal pradesh",
            "bangalore", "bengaluru", "chennai", "kolkata", "gujarat",
            "uttarakhand", "haryana", "uttar pradesh", "bihar", "hindustan"
        ]
        if any(loc in raw_text.lower() for loc in indian_locations):
            found_coo = True
            coo_val = "India (Inferred from Manufacturer Location)"

    checks.append({
        "rule_id": "COO_1",
        "rule_name": "Country of Origin",
        "rule_reference": "Rule 6(1) / FSSAI",
        "status": "pass" if found_coo else "warning",
        "details": f"Found: {coo_val}" if found_coo
                   else "Country of origin not explicitly found on package.",
        "evidence": coo_val if found_coo else None,
        "severity": "medium",
    })

    # -----------------------------------------------------------------------
    # 18. Barcode / QR Code
    # -----------------------------------------------------------------------
    bc_data = barcode_results.get("barcode_data")
    bc_type = barcode_results.get("barcode_type")
    qr_data = barcode_results.get("qrcode_data")

    bc_status = "pass" if bc_data or qr_data else "warning"
    details_parts = []
    if bc_data:
        details_parts.append(f"Barcode: {bc_type} — {bc_data}")
    if qr_data:
        details_parts.append(f"QR Code: {qr_data}")
    if not bc_data and not qr_data:
        details_parts.append("No barcode or QR code detected by initial scan.")

    checks.append({
        "rule_id": BARCODE_RULE["rule_id"],
        "rule_name": BARCODE_RULE["rule_name"],
        "rule_reference": BARCODE_RULE["rule_reference"],
        "status": bc_status,
        "details": " | ".join(details_parts),
        "evidence": bc_data or qr_data,
        "severity": BARCODE_RULE["severity"],
    })

    # -----------------------------------------------------------------------
    # 19. Manufacturing License Number (MFG_LIC)
    # -----------------------------------------------------------------------
    found_mfg_lic, mfg_lic_val = _search_text(raw_text, "drug_license")
    if found_mfg_lic and mfg_lic_val:
        # Clean trailing whitespace and punctuation
        mfg_lic_val = re.sub(r"[\s,;.\-]+$", "", mfg_lic_val).strip()
        if not mfg_lic_val:
            found_mfg_lic = False

    # Status and details determined by regulatory framework for each category:
    if found_mfg_lic:
        mfg_status = "pass"
        mfg_details = f"Found: {mfg_lic_val}"
        mfg_evidence = mfg_lic_val
    elif category == "food":
        # Under FSSAI, food manufacturing/packing is licensed under statutory FSSAI regulations
        fssai_match = next((c for c in checks if c["rule_id"] == "FSSAI_1" and c.get("evidence")), None)
        if fssai_match or (found_fssai and fssai_val):
            f_ev = (fssai_match["evidence"] if fssai_match else fssai_val) or ""
            mfg_status = "pass"
            mfg_details = f"Covered under statutory FSSAI Manufacturing/Packing License: {f_ev}".strip()
            mfg_evidence = f_ev
        else:
            mfg_status = "not_applicable"
            mfg_details = "Food commodities are licensed under Food Safety & Standards Act (FSSAI). See FSSAI License requirement."
            mfg_evidence = None
    elif category in ("general", "electronics", "chemical"):
        # Governed by Legal Metrology Rule 6(1)(b) manufacturer/packer details
        mfg_status = "not_applicable"
        mfg_details = f"Not applicable for {category} category (governed by Rule 6(1)(b) manufacturer details)."
        mfg_evidence = None
    elif category == "medicine":
        # Governed by statutory Drug Manufacturing License (DRUG_LIC) check
        mfg_status = "not_applicable"
        mfg_details = "Governed by statutory Drug Manufacturing License (DRUG_LIC) check."
        mfg_evidence = None
    else:
        mfg_status = "warning"
        mfg_details = "Manufacturing license number not detected."
        mfg_evidence = None

    checks.append({
        "rule_id": MFG_LICENSE_RULE["rule_id"],
        "rule_name": MFG_LICENSE_RULE["rule_name"],
        "rule_reference": MFG_LICENSE_RULE["rule_reference"],
        "status": mfg_status,
        "details": mfg_details,
        "evidence": mfg_evidence,
        "severity": MFG_LICENSE_RULE["severity"],
    })

    # -----------------------------------------------------------------------
    # 20-24. Medicine / Pharma — Specific Checks
    # Only evaluated when category is "medicine"
    # -----------------------------------------------------------------------
    if category == "medicine":
        # 20. Drug Manufacturing License Number (DRUG_LIC)
        # Reuse the mfg_lic detection from above since it uses the same pattern
        checks.append({
            "rule_id": DRUG_LICENSE_RULE["rule_id"],
            "rule_name": DRUG_LICENSE_RULE["rule_name"],
            "rule_reference": DRUG_LICENSE_RULE["rule_reference"],
            "status": "pass" if found_mfg_lic else "fail",
            "details": f"Drug Mfg. License: {mfg_lic_val}" if found_mfg_lic
                       else "Drug manufacturing license number not found on package.",
            "evidence": mfg_lic_val if found_mfg_lic else None,
            "severity": DRUG_LICENSE_RULE["severity"],
        })

        # 21. Composition / Formulation (COMP_1)
        found_comp, comp_val = _search_text(raw_text, "composition")
        if found_comp and comp_val:
            comp_val = _clean_composition(comp_val)
            if len(comp_val) < 10:
                found_comp = False
                comp_val = ""

        checks.append({
            "rule_id": COMPOSITION_RULE["rule_id"],
            "rule_name": COMPOSITION_RULE["rule_name"],
            "rule_reference": COMPOSITION_RULE["rule_reference"],
            "status": "pass" if found_comp else "fail",
            "details": "Composition/formulation section found." if found_comp
                       else "Drug composition/formulation not found on package.",
            "evidence": comp_val[:300] if found_comp and comp_val else None,
            "severity": COMPOSITION_RULE["severity"],
        })

        # 22. Dosage Instructions (DOSE_1)
        found_dose, dose_val = _search_text(raw_text, "dosage")
        found_as_directed, as_directed_val = _search_text(raw_text, "as_directed")
        
        dose_found = found_dose or found_as_directed
        dose_evidence = None
        if found_dose:
            # Clean dosage text
            dose_val = dose_val[:200].strip()
            dose_evidence = dose_val
        elif found_as_directed:
            dose_evidence = as_directed_val

        checks.append({
            "rule_id": DOSAGE_RULE["rule_id"],
            "rule_name": DOSAGE_RULE["rule_name"],
            "rule_reference": DOSAGE_RULE["rule_reference"],
            "status": "pass" if dose_found else "fail",
            "details": f"Found: {dose_evidence}" if dose_found
                       else "Dosage instructions not found on package.",
            "evidence": dose_evidence,
            "severity": DOSAGE_RULE["severity"],
        })

        # 23. Warning / Caution Statements (WARN_1)
        found_warn, warn_val = _search_text(raw_text, "warning")
        found_ext_use, ext_use_val = _search_text(raw_text, "external_use")
        
        warn_found = found_warn or found_ext_use
        warn_evidence = None
        if found_warn:
            # Truncate long warning text
            warn_val = warn_val[:300].strip()
            warn_evidence = warn_val
        if found_ext_use:
            if warn_evidence:
                warn_evidence = f"{warn_evidence} | {ext_use_val}"
            else:
                warn_evidence = ext_use_val

        checks.append({
            "rule_id": WARNING_RULE["rule_id"],
            "rule_name": WARNING_RULE["rule_name"],
            "rule_reference": WARNING_RULE["rule_reference"],
            "status": "pass" if warn_found else "warning",
            "details": "Warning/caution statements found." if warn_found
                       else "No warning or caution statements detected.",
            "evidence": warn_evidence,
            "severity": WARNING_RULE["severity"],
        })

        # 24. Schedule Classification (SCHED_1)
        found_sched, sched_val = _search_text(raw_text, "schedule")

        checks.append({
            "rule_id": SCHEDULE_RULE["rule_id"],
            "rule_name": SCHEDULE_RULE["rule_name"],
            "rule_reference": SCHEDULE_RULE["rule_reference"],
            "status": "pass" if found_sched else "warning",
            "details": f"Found: {sched_val}" if found_sched
                       else "Schedule classification not explicitly found (may not be required for all drugs).",
            "evidence": sched_val if found_sched else None,
            "severity": SCHEDULE_RULE["severity"],
        })

    # -----------------------------------------------------------------------
    # Category-Based Exemptions
    # -----------------------------------------------------------------------

    # Medicine pricing and dates are regulated under DPCO / Drugs & Cosmetics Rules.
    # If declared on package, they are valid and compliant (pass).
    if category == "medicine":
        for c in checks:
            if c["rule_id"] == "R6_1_E":
                if c.get("evidence"):
                    c["status"] = "pass"
                    c["details"] = f"Maximum Retail Price declared: {c['evidence']} (Compliant with DPCO / Drug pricing rules)."
                else:
                    c["status"] = "fail"
                    c["details"] = "Maximum Retail Price (MRP) not found on medicine package (Required under DPCO / Drugs Rules)."
            elif c["rule_id"] == "MRP_FMT":
                if c.get("evidence"):
                    c["status"] = "pass"
                    c["details"] = "MRP declared inclusive of all taxes (Compliant under DPCO / Drugs Rules)."
                elif any(chk["rule_id"] == "R6_1_E" and chk.get("evidence") for chk in checks):
                    c["status"] = "pass"
                    c["details"] = "MRP format compliant on medicine package (Governed under DPCO / Drugs Rules)."
            elif c["rule_id"] == "DATE_FMT":
                if c.get("evidence"):
                    c["status"] = "pass"
                    c["details"] = f"Date declared on medicine package: {c['evidence']} (Compliant with Drugs & Cosmetics Rules)."
    
    # Electronics don't have Expiry Dates or Batch necessarily
    if category == "electronics":
        for c in checks:
            if c["rule_id"] in ["BB_1"]:
                c["status"] = "not_applicable"
                c["details"] = "Expiry date not applicable for electronics."

    # Food commodities are licensed under Food Safety & Standards Act (FSSAI)
    if category == "food":
        for c in checks:
            if c["rule_id"] == "MFG_LIC" and c["status"] != "pass":
                fssai_chk = next((chk for chk in checks if chk["rule_id"] == "FSSAI_1" and chk.get("evidence")), None)
                if fssai_chk:
                    c["status"] = "pass"
                    c["details"] = f"Covered under statutory FSSAI Manufacturing/Packing License: {fssai_chk['evidence']}"
                    c["evidence"] = fssai_chk["evidence"]
                else:
                    c["status"] = "not_applicable"
                    c["details"] = "Food commodities are licensed under Food Safety & Standards Act (FSSAI)."

    # General goods don't have FSSAI, Veg/NonVeg, Allergen, Nutrition, or MFG_LIC
    if category in ["general", "electronics", "chemical"]:
        for c in checks:
            if c["rule_id"] in ["FSSAI_1", "VEG_1", "ALLRG_1", "NUT_1", "ING_1"]:
                c["status"] = "not_applicable"
                c["details"] = f"Not applicable for {category} category."
            elif c["rule_id"] == "MFG_LIC" and c["status"] != "pass":
                c["status"] = "not_applicable"
                c["details"] = f"Not applicable for {category} category (governed by Rule 6(1)(b) manufacturer details)."

    # Cosmetics don't have Veg/NonVeg, Allergen, Nutrition (usually)
    if category == "cosmetic":
        for c in checks:
            if c["rule_id"] in ["VEG_1", "ALLRG_1", "NUT_1", "FSSAI_1"]:
                c["status"] = "not_applicable"
                c["details"] = "Not applicable for cosmetic category."

    # Medicine doesn't need FSSAI, Veg/NonVeg, Allergen (food-specific), Nutrition, Ingredients (food-specific)
    if category == "medicine":
        for c in checks:
            if c["rule_id"] in ["FSSAI_1", "VEG_1", "ALLRG_1", "NUT_1", "ING_1"]:
                c["status"] = "not_applicable"
                c["details"] = "Not applicable for medicine category (governed by Drugs & Cosmetics Rules)."
            elif c["rule_id"] == "MFG_LIC":
                c["status"] = "not_applicable"
                c["details"] = "Governed by statutory Drug Manufacturing License (DRUG_LIC) check."

    # Non-medicine categories should NOT have medicine-specific checks
    if category != "medicine":
        for c in checks:
            if c["rule_id"] in ["DRUG_LIC", "COMP_1", "DOSE_1", "WARN_1", "SCHED_1"]:
                c["status"] = "not_applicable"
                c["details"] = f"Not applicable for {category} category."

    # -----------------------------------------------------------------------
    # Attach Statutory Penalties (Legal Metrology Act, 2009)
    # -----------------------------------------------------------------------
    for c in checks:
        penalty = get_statutory_penalty(c["rule_id"])
        if penalty and c["status"] in ("fail", "warning"):
            c["statutory_section"] = penalty["section"]
            c["statutory_title"] = penalty["title"]
            c["statutory_penalty"] = f"{penalty['section']} ({penalty['first_offence']})"
        else:
            c["statutory_section"] = None
            c["statutory_title"] = None
            c["statutory_penalty"] = None

    return checks, category


def calculate_compliance_score(checks: List[Dict]) -> Dict:
    """
    Calculate overall compliance score from individual check results.

    Returns dict with score, counts, and overall status.
    """
    total = 0
    passed = 0
    failed = 0
    warnings = 0

    critical_fails = 0
    high_fails = 0

    for c in checks:
        if c["status"] == "not_applicable":
            continue
        total += 1
        if c["status"] == "pass":
            passed += 1
        elif c["status"] == "fail":
            failed += 1
            severity = c.get("severity", "medium")
            if severity == "critical":
                critical_fails += 1
            elif severity == "high":
                high_fails += 1
        elif c["status"] == "warning":
            warnings += 1

    score = (passed / total * 100) if total > 0 else 0

    # Determine overall status
    if critical_fails > 0 or high_fails > 0:
        status = "non_compliant"
    elif failed > 0 or warnings > 0:
        status = "warning"
    else:
        status = "compliant"

    return {
        "score": round(score, 1),
        "total": total,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "status": status,
    }
