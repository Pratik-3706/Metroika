"""
Compliance engine — the PRIMARY compliance checker.

Validates OCR-extracted label data against:
- Legal Metrology (Packaged Commodities) Rules, 2011
- FSSAI regulations
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
    validate_mrp_format,
    validate_date_format,
    validate_net_quantity,
    get_min_font_height,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enhanced Regex Patterns for field extraction
# ---------------------------------------------------------------------------

PATTERNS = {
    # Manufacturer / Packer / Importer details
    "manufacturer": re.compile(
        r"(?:Mfd\.?\s*(?:by)?|Manufactured\s*(?:by)?|Mfr\.?\s*(?:by)?|"
        r"Mktd\.?\s*(?:by)?|Marketed\s*(?:by)?|"
        r"Packed\s*(?:by)?|Packer\s*|"
        r"Imported\s*(?:by)?|Importer\s*)"
        r"[\s:.\-]*"
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
        r"(?:\s*(?:IN\s+MUMBAI|O/?S\s+MUMBAI|IN\s+DELHI|O/?S\s+DELHI))?"
        r"[\s:.\-]*"
        r"(?:Rs\.?\s*|₹\s*|INR\s*)?"
        r"([\d,]+\.?\s*\d*)"
        r"(?:\s*/?\s*-)?",
        re.IGNORECASE,
    ),

    # Manufacture / Packing Date — various formats
    "manufacture_date": re.compile(
        r"(?:Mfg\.?\s*(?:Date|Dt)?\.?|Mfd\.?\s*(?:Date|Dt)?\.?|"
        r"Pkd\.?\s*(?:Date|Dt)?\.?|Pkdt\.?|"
        r"Pkg\.?\s*(?:Date|Dt)?\.?|"
        r"Date\s*of\s*(?:Mfg|Manufacture|Packing|Pkg)\.?)"
        r"[\s:.\-]*"
        r"(\d{1,2}[\s/\-.]?\d{1,2}[\s/\-.]?\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{2,4}|"
        r"\d{1,2}[\s/\-.]?\d{2,4})",
        re.IGNORECASE,
    ),

    # Best Before / Expiry / Use By
    "best_before": re.compile(
        r"(?:Best\s*Before|BB|Use\s*(?:By|Before)|Exp(?:iry)?\.?\s*(?:Date)?\.?|"
        r"Shelf\s*Life)"
        r"[\s:.\-]*"
        r"(\d+\s*(?:days?|months?|years?|D|M|Y)|"
        r"\d{1,2}[\s/\-.]?\d{1,2}[\s/\-.]?\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{2,4}|"
        r"\d{1,2}[\s/\-.]?\d{2,4})",
        re.IGNORECASE,
    ),

    # Batch Number
    "batch_number": re.compile(
        r"(?:B\.?\s*No\.?|Batch\s*(?:No\.?|Number)|Lot\s*(?:No\.?|Number))"
        r"[\s:.\-]*"
        r"([A-Za-z0-9\-/]+\d[A-Za-z0-9\-/]*)",
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

    # Inclusive of all taxes
    "inclusive_taxes": re.compile(
        r"(?:incl(?:usive)?\.?\s*(?:of\s+)?all\s+taxes?|"
        r"incl\.?\s*of\s+all\s+taxes|"
        r"inclusive\s+of\s+all\s+taxes)",
        re.IGNORECASE,
    ),

    # Country of Origin
    "country_of_origin": re.compile(
        r"(?:Country\s*of\s*Origin|Made\s*in|Product\s*of)"
        r"[\s:.\-]*"
        r"([A-Za-z\s]+)",
        re.IGNORECASE,
    ),

    # Ingredients
    "ingredients": re.compile(
        r"(?:Ingredients?\s*[:.])\s*(.{10,})",
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

    # Storage instructions
    "storage": re.compile(
        r"(?:Store|Keep|Storage)\s*(?:in|at)?\s*"
        r"(?:a\s*)?(?:cool|dry|room\s*temp|refrigerat|below|away)",
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
        # Return the full match or the first group if available
        try:
            return True, match.group(1).strip() if match.groups() else match.group(0).strip()
        except (IndexError, AttributeError):
            return True, match.group(0).strip()
    return False, ""


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


# ---------------------------------------------------------------------------
# Product Category Detection
# ---------------------------------------------------------------------------
def detect_product_category(raw_text: str) -> str:
    """Detect product category based on OCR text heuristics."""
    text_lower = raw_text.lower()
    
    # Medicines
    if any(kw in text_lower for kw in ["schedule h", "rx", "medical practitioner", "dpco", "schedule-h", "schedule g"]):
        return "medicine"
        
    # Cosmetics
    if any(kw in text_lower for kw in ["cosmetic", "inci", "external use only"]):
        return "cosmetic"
        
    # Food
    if any(kw in text_lower for kw in ["fssai", "nutrition", "veg", "food", "edible"]):
        return "food"
        
    # Chemicals
    if any(kw in text_lower for kw in ["poison", "hazard", "danger", "insecticide", "pesticide"]):
        return "chemical"
        
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
    manual_category: Optional[str] = None
) -> Tuple[List[Dict], str]:
    """
    Run all compliance checks against raw OCR text.

    This is the PRIMARY compliance engine. AI only verifies these results.

    Args:
        raw_text: Concatenated OCR text from all images.
        barcode_results: Output from barcode scanner.
        structured_ocr: Optional structured OCR data with bounding boxes.
        manual_category: Optional manual override from UI.

    Returns:
        (List of compliance check result dicts, detected category)
    """
    if manual_category and manual_category.strip() and manual_category != "auto":
        category = manual_category.strip().lower()
    else:
        category = detect_product_category(raw_text)

    checks: List[Dict] = []

    # -----------------------------------------------------------------------
    # 1. Product Name (R6_1_A) — Hard to regex, use heuristic
    # -----------------------------------------------------------------------
    # Look for prominent text that could be the product name
    # In structured OCR, this is typically the largest/earliest text block
    product_name_found = False
    product_name_evidence = None

    if structured_ocr:
        # Check if any OCR result has large text at the top of any image
        for img_path, ocr_items in structured_ocr.items():
            if ocr_items:
                # First few text blocks are often the product name
                top_texts = [item["text"] for item in ocr_items[:3]
                             if item["confidence"] > 0.7 and len(item["text"]) > 2]
                
                for text_val in top_texts:
                    text_lower = text_val.lower()
                    if any(kw in text_lower for kw in ["batch", "mfg", "exp", "mrp", "net", "price", "date"]):
                        continue
                    product_name_found = True
                    product_name_evidence = text_val
                    break
                
                if product_name_found:
                    break

    checks.append({
        "rule_id": "R6_1_A",
        "rule_name": "Product Name",
        "rule_reference": "Rule 6(1)(a)",
        "status": "pass" if product_name_found else "warning",
        "details": f"Detected: {product_name_evidence}" if product_name_found
                   else "Product name detection requires visual verification.",
        "evidence": product_name_evidence,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 2. Manufacturer / Packer / Importer Details (R6_1_B)
    # -----------------------------------------------------------------------
    found, val = _search_text(raw_text, "manufacturer")
    if not found:
        # Fallback: look for common company suffixes
        found, val = _search_with_fallback(
            raw_text, "manufacturer",
            r"([A-Z][A-Za-z\s]+(?:Pvt\.?\s*Ltd\.?|Limited|Industries|Corp|Inc|LLP|P\.?O\.?\s*Box))"
        )

    checks.append({
        "rule_id": "R6_1_B",
        "rule_name": "Manufacturer / Packer Details",
        "rule_reference": "Rule 6(1)(b)",
        "status": "pass" if found else "fail",
        "details": f"Found: {val}" if found else "Manufacturer/Packer details not found on package.",
        "evidence": val if found else None,
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

    # Find all raw dates in the document for fallbacks
    all_raw_dates = re.findall(r"\b\d{1,2}[\s/\-.]\d{1,2}[\s/\-.]\d{2,4}\b", raw_text)

    # -----------------------------------------------------------------------
    # 4. Manufacture / Packing Date (R6_1_D)
    # -----------------------------------------------------------------------
    found, val = _search_text(raw_text, "manufacture_date")
    if not found:
        # Fallback: look for date-like patterns near keywords
        fallback = re.search(
            r"(?:Mfg|Mfd|Pkd|Pkdt)[\s:.]*(\d{1,2}[\s/\-.]?\d{1,2}[\s/\-.]?\d{2,4})",
            raw_text, re.IGNORECASE
        )
        if fallback:
            found = True
            val = fallback.group(1).strip()
        elif all_raw_dates:
            # Aggressive fallback: assume the first raw date in the document is the manufacturing/packing date
            found = True
            val = all_raw_dates[0] + " (inferred)"

    checks.append({
        "rule_id": "R6_1_D",
        "rule_name": "Manufacture / Packing Date",
        "rule_reference": "Rule 6(1)(d)",
        "status": "pass" if found else "fail",
        "details": f"Found: {val}" if found else "Manufacture/packing date not found on package.",
        "evidence": val if found else None,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 5. Maximum Retail Price (R6_1_E)
    # -----------------------------------------------------------------------
    found_mrp, mrp_val = _search_text(raw_text, "mrp")
    if not found_mrp:
        # Fallback: simpler MRP pattern
        fallback = re.search(
            r"(?:MRP|M\.?R\.?P\.?)[\s:.\-]*(?:Rs\.?\s*|₹\s*)?(\d[\d,]*\.?\d*)",
            raw_text, re.IGNORECASE
        )
        if fallback:
            found_mrp = True
            mrp_val = fallback.group(1).strip()

    checks.append({
        "rule_id": "R6_1_E",
        "rule_name": "Maximum Retail Price (MRP)",
        "rule_reference": "Rule 6(1)(e)",
        "status": "pass" if found_mrp else "fail",
        "details": f"MRP found: Rs. {mrp_val}" if found_mrp else "MRP not found on package.",
        "evidence": f"Rs. {mrp_val}" if found_mrp else None,
        "severity": "high",
    })

    # -----------------------------------------------------------------------
    # 5b. MRP Format — "Inclusive of all taxes" (MRP_FMT)
    # -----------------------------------------------------------------------
    found_taxes, taxes_val = _search_text(raw_text, "inclusive_taxes")

    mrp_fmt_status = "pass" if (found_mrp and found_taxes) else "fail" if found_mrp else "warning"
    mrp_fmt_details = ""
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

    consumer_found = found_phone or found_email or found_toll
    consumer_evidence_parts = []
    if found_phone:
        consumer_evidence_parts.append(f"Phone: {phone_val}")
    if found_email:
        consumer_evidence_parts.append(f"Email: {email_val}")
    if found_toll:
        consumer_evidence_parts.append(f"Toll-free: {toll_val}")

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
    # 8. List of Ingredients
    # -----------------------------------------------------------------------
    found_ing, ing_val = _search_text(raw_text, "ingredients")
    if not found_ing:
        # Fallback check for the keyword alone
        found_ing = bool(re.search(r"ingredients?\s*[:.]", raw_text, re.IGNORECASE))

    checks.append({
        "rule_id": "ING_1",
        "rule_name": "List of Ingredients",
        "rule_reference": "Rule 6(1)(b) / FSSAI",
        "status": "pass" if found_ing else "fail",
        "details": "Ingredients section found." if found_ing
                   else "Ingredients list not found on package.",
        "evidence": ing_val[:100] if found_ing and ing_val else None,
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

    checks.append({
        "rule_id": "NUT_1",
        "rule_name": "Nutritional Information",
        "rule_reference": "FSSAI",
        "status": "pass" if nut_found else "fail",
        "details": "Nutritional information section found." if nut_found
                   else "Nutritional information not found on package.",
        "evidence": nut_val if found_nut else None,
        "severity": "medium",
    })

    # -----------------------------------------------------------------------
    # 10. Best Before / Expiry Date
    # -----------------------------------------------------------------------
    found_bb, bb_val = _search_text(raw_text, "best_before")
    if not found_bb:
        if len(all_raw_dates) >= 2:
            # If multiple dates exist, assume the last one is the expiry/best before
            found_bb = True
            bb_val = all_raw_dates[-1] + " (inferred)"
        elif len(all_raw_dates) == 1 and not found:
            # If only one date exists and wasn't used for Mfg
            found_bb = True
            bb_val = all_raw_dates[0] + " (inferred)"

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
    # 11. Batch Number
    # -----------------------------------------------------------------------
    found_batch, batch_val = _search_text(raw_text, "batch_number")
    if not found_batch:
        # Fallback: Look for standalone lot/batch-like codes (e.g. D1355, L2-1)
        fallback = re.search(
            r"\b([A-Z]{1,2}\d{3,}[A-Z0-9\-]*|\d{4,}[A-Z]{2,})\b", 
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
    # 14. Storage Instructions
    # -----------------------------------------------------------------------
    found_storage, storage_val = _search_text(raw_text, "storage")

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
    # 15. Font Size Compliance (R7_FONT) — visual check
    # -----------------------------------------------------------------------
    checks.append({
        "rule_id": FONT_SIZE_RULE["rule_id"],
        "rule_name": FONT_SIZE_RULE["rule_name"],
        "rule_reference": FONT_SIZE_RULE["rule_reference"],
        "status": "pass",
        "details": "Assumed compliant (requires physical measurement).",
        "evidence": None,
        "severity": FONT_SIZE_RULE["severity"],
    })

    # -----------------------------------------------------------------------
    # 16. Principal Display Panel (R8_PDP) — visual check
    # -----------------------------------------------------------------------
    checks.append({
        "rule_id": PDP_RULE["rule_id"],
        "rule_name": PDP_RULE["rule_name"],
        "rule_reference": PDP_RULE["rule_reference"],
        "status": "pass",
        "details": "Assumed compliant (requires visual inspection).",
        "evidence": None,
        "severity": PDP_RULE["severity"],
    })

    # -----------------------------------------------------------------------
    # 17. Language of Declarations (R6_LANG) — visual check
    # -----------------------------------------------------------------------
    checks.append({
        "rule_id": LANGUAGE_RULE["rule_id"],
        "rule_name": LANGUAGE_RULE["rule_name"],
        "rule_reference": LANGUAGE_RULE["rule_reference"],
        "status": "pass",
        "details": "Assumed compliant (requires visual inspection).",
        "evidence": None,
        "severity": LANGUAGE_RULE["severity"],
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
        "evidence": bc_data,
        "severity": BARCODE_RULE["severity"],
    })

    # Conditionally remove or mark rules based on category
    # Medicine exempt from standard MRP and Date Format (has strict DPCO/Drug rules)
    if category == "medicine":
        checks = [c for c in checks if c["rule_id"] not in ["R6_1_E", "MRP_FMT", "DATE_FMT"]]
    
    # Electronics don't have Expiry Dates or Batch necessarily
    if category == "electronics":
        for c in checks:
            if c["rule_id"] in ["BB_1"]:
                c["status"] = "not_applicable"
                c["details"] = "Expiry date not applicable for electronics."

    # General goods don't have FSSAI, Veg/NonVeg, Allergen, Nutrition
    if category in ["general", "electronics", "chemical"]:
        for c in checks:
            if c["rule_id"] in ["FSSAI_1", "VEG_1", "ALLRG_1", "NUT_1", "ING_1"]:
                c["status"] = "not_applicable"
                c["details"] = f"Not applicable for {category} category."

    # Cosmetics don't have Veg/NonVeg, Allergen, Nutrition (usually)
    if category == "cosmetic":
        for c in checks:
            if c["rule_id"] in ["VEG_1", "ALLRG_1", "NUT_1", "FSSAI_1"]:
                c["status"] = "not_applicable"
                c["details"] = "Not applicable for cosmetic category."

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
