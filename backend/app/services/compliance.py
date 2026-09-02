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

# Stop-phrases that signal end of a manufacturer/address field
_MANUFACTURER_STOP_PHRASES = re.compile(
    r"(?:DO\s*NOT\s*BUY|SCAN\s*HERE|FOR\s*MRP|FOR\s*MFR|READ\s*THE|AS\s*COMPARED|"
    r"FSSAI|INGREDIENTS|NUTRITION|ALLERGEN|STORE\s|KEEP\s|NET\s*(?:WT|WEIGHT|QTY)|"
    r"BEST\s*BEFORE|USE\s*(?:BY|BEFORE|WITHIN)|MFG\.?\s*BY|MFD\.?\s*BY|"
    r"TOLL\s*FREE|CUSTOMER\s*CARE|CONSUMER\s*CARE|BATCH|"
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
        r"(?:Rs\.?\s*|₹\s*|INR\s*|Rupees?\s*)?"
        r"([\d,]+\.?\d*)"
        r"(?:\s*/?\s*-)?",
        re.IGNORECASE,
    ),

    # Manufacture / Packing Date — various formats (supports 2-digit years like DD/MM/YY)
    "manufacture_date": re.compile(
        r"(?:Mfg\.?\s*(?:Date|Dt)?\.?|Mfd\.?\s*(?:Date|Dt)?\.?|"
        r"Pkd\.?\s*(?:Date|Dt)?\.?|Pkdt\.?|"
        r"Pkg\.?\s*(?:Date|Dt)?\.?|"
        r"Date\s*of\s*(?:Mfg|Manufacture|Packing|Pkg)\.?)"
        r"[\s:.\-]*"
        r"(\d{1,2}[\s/\-.]\d{1,2}[\s/\-.]\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{2,4}|"
        r"\d{1,2}[\s/\-.]\d{2,4})",
        re.IGNORECASE,
    ),

    # Best Before / Expiry / Use By
    "best_before": re.compile(
        r"(?:Best\s*Before|BB|Use\s*(?:By|Before)|Exp(?:iry)?\.?\s*(?:Date)?\.?|"
        r"Shelf\s*Life)"
        r"[\s:.\-]*"
        r"(\d+\s*(?:days?|months?|years?|D|M|Y)|"
        r"\d{1,2}[\s/\-.]\d{1,2}[\s/\-.]\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{2,4}|"
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
        r"(?:B\.?\s*No\.?|Batch\s*(?:No\.?|Number)|Lot\s*(?:No\.?|Number))"
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
        r"(?:a\s*)?(?:cool|dry|room\s*temp|refrigerat|below|away)[^.]*\.?)",
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
# Product Category Detection
# ---------------------------------------------------------------------------
def detect_product_category(raw_text: str) -> str:
    """Detect product category based on OCR text heuristics."""
    text_lower = raw_text.lower()
    
    # Medicines
    if any(kw in text_lower for kw in ["schedule h", "rx", "medical practitioner", "dpco", "schedule-h", "schedule g"]):
        return "medicine"
        
    # Food — check before cosmetics since FSSAI/nutrition keywords are more reliable
    if any(kw in text_lower for kw in ["fssai", "nutrition", "food", "edible"]):
        return "food"
        
    # Cosmetics — use word-boundary for 'inci' to avoid false positive on 'Incl.'
    cosmetic_keywords = ["cosmetic", "external use only"]
    if any(kw in text_lower for kw in cosmetic_keywords) or re.search(r"\binci\b", text_lower):
        return "cosmetic"
        
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
    # 1. Product Name (R6_1_A) — Improved heuristic with keyword detection
    # -----------------------------------------------------------------------
    product_name_found = False
    product_name_evidence = None

    # Common product-type keywords to help identify actual product names
    _PRODUCT_TYPE_KEYWORDS = [
        "ketchup", "sauce", "jam", "juice", "biscuit", "cookie", "chips",
        "noodles", "pasta", "rice", "flour", "oil", "soap", "shampoo",
        "cream", "lotion", "powder", "tea", "coffee", "milk", "butter",
        "cheese", "chocolate", "candy", "cereal", "bread", "water",
        "drink", "beverage", "snack", "masala", "spice", "pickle",
        "yogurt", "curd", "paneer", "ghee", "honey", "sugar", "salt",
        "detergent", "cleaner", "toothpaste", "deodorant", "perfume",
        "tablet", "capsule", "syrup", "ointment", "gel", "spray",
    ]
    # Words that should NOT be treated as product names
    _NOT_PRODUCT_NAME = [
        "per serve", "perserve", "per 100", "nutrition", "ingredients",
        "energy", "protein", "carbohydrate", "fat", "sugar", "sodium",
        "calories", "kcal", "rda", "dietary", "fibre", "cholesterol",
        "serving", "approx", "typical", "values", "information",
        "mktd", "mfg", "mfd", "manufactured", "marketed", "packed",
        "batch", "fssai", "lic", "regn", "toll free", "scan here",
    ]

    # Strategy 1: Search OCR text for brand + product type patterns
    for product_kw in _PRODUCT_TYPE_KEYWORDS:
        # Look for "BrandName ProductType" or "BrandName® ProductType" patterns
        pattern = re.compile(
            r"([A-Z][A-Za-z']+(?:\s+[A-Z][A-Za-z']+)*)\s+" + re.escape(product_kw),
            re.IGNORECASE
        )
        match = pattern.search(raw_text)
        if match:
            candidate = match.group(0).strip()
            # Verify it's not a false positive from nutrition table
            if not any(bad in candidate.lower() for bad in _NOT_PRODUCT_NAME):
                product_name_found = True
                product_name_evidence = candidate
                break

    # Strategy 2: If structured OCR available, look for large/prominent text blocks
    if not product_name_found and structured_ocr:
        for img_path, ocr_items in structured_ocr.items():
            if ocr_items:
                # Filter to high-confidence text blocks that aren't noise
                candidates = [
                    item["text"] for item in ocr_items[:5]
                    if item["confidence"] > 0.7
                    and len(item["text"]) > 2
                    and not any(bad in item["text"].lower() for bad in _NOT_PRODUCT_NAME)
                ]
                if candidates:
                    product_name_found = True
                    product_name_evidence = candidates[0]
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

    # Clean manufacturer text to remove trailing garbage
    if found and val:
        val = _clean_manufacturer(val)
        if not val:
            found = False

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

    # Find all raw dates in the document for fallbacks (avoiding phone numbers)
    all_raw_dates = re.findall(r"(?<![\d\-])\d{1,2}[\s/\-.]\d{1,2}[\s/\-.]\d{2,4}(?![\d\-])", raw_text)

    # -----------------------------------------------------------------------
    # 4. Manufacture / Packing Date (R6_1_D)
    # -----------------------------------------------------------------------
    found_mfg, mfg_val = _search_text(raw_text, "manufacture_date")
    if not found_mfg:
        # Fallback: look for date-like patterns near keywords (supports 2-digit year)
        fallback = re.search(
            r"(?:Mfg|Mfd|Pkd|Pkdt)[\s:.]*(\d{1,2}[\s/\-.]\d{1,2}[\s/\-.]\d{2,4})",
            raw_text, re.IGNORECASE
        )
        if fallback:
            found_mfg = True
            mfg_val = fallback.group(1).strip()
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
        r"(?:\s*(?:IN\s+MUMBAI|O/?S\s+MUMBAI|IN\s+DELHI|O/?S\s+DELHI))?"
        r"[\s:.\-]*"
        r"(?:Rs\.?\s*|₹\s*|INR\s*|Rupees?\s*)?"
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
        # Fallback: Standalone currency amounts (₹140, Rs. 140, 140/- or 1401- due to OCR)
        # Only applied if we failed to find an explicit MRP keyword attached to a number
        fallback_pattern = re.compile(
            r"(?:Rs\.?\s+|₹\s*|INR\s+|Rupees?\s+)([\d,]+\.?\d*)|([\d,]+\.?\d*)\s*(?:/-)",
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
                
            # Ignore tiny values like 0 or 1 which are likely OCR errors (e.g. from dates like 01-)
            if val_num <= 1:
                continue
                
            if val_num > best_fallback_score:
                best_fallback_score = val_num
                best_fallback_mrp = val_str.strip()
                
        if best_fallback_mrp is not None:
            found_mrp = True
            mrp_val = best_fallback_mrp

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
            # Last resort: just check if the keyword exists at all
            found_ing = bool(re.search(r"ingredients?\s*[:.]", raw_text, re.IGNORECASE))
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

    # If primary pattern didn't find it, try "use within X months" pattern
    if not found_bb:
        found_bb, bb_val = _search_text(raw_text, "use_within")
        if found_bb:
            bb_val = f"Use within {bb_val}"

    if not found_bb:
        # Fallback to inferred dates — but validate them first
        if len(all_raw_dates) >= 2:
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
            # There's a reference to use-by date but it's on the bottom of the pack
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
            r"(?:\.|FSSAI|PLEASE|LIC|HUL|FOR\s|\bAND\b)",
            batch_val, flags=re.IGNORECASE
        )[0].strip()
        # Remove trailing whitespace/punctuation
        batch_val = re.sub(r"[\s,;.\-]+$", "", batch_val)
        if not batch_val:
            found_batch = False

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
    # 14. Storage Instructions — find all matches, pick the cleanest one
    # -----------------------------------------------------------------------
    storage_pattern = re.compile(
        r"((?:Store|Keep|Storage)\s*(?:in|at)?\s*"
        r"(?:a\s*)?(?:cool|dry|room\s*temp|refrigerat|below|away)[^.]*\.?)",
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
    # 17b. Country of Origin (COO_1)
    # -----------------------------------------------------------------------
    found_coo, coo_val = _search_text(raw_text, "country_of_origin")
    if found_coo:
        # Clean up: strip trailing junk
        coo_val = re.sub(r"[^A-Za-z\s]", "", coo_val).strip()
        if len(coo_val) < 2:
            found_coo = False
            coo_val = ""

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
        "evidence": bc_data,
        "severity": BARCODE_RULE["severity"],
    })

    # Conditionally remove or mark rules based on category
    # Medicine exempt from standard MRP and Date Format (has strict DPCO/Drug rules)
    if category == "medicine":
        for c in checks:
            if c["rule_id"] in ["R6_1_E", "MRP_FMT", "DATE_FMT"]:
                c["status"] = "not_applicable"
                c["details"] = "Not applicable under Legal Metrology (governed by DPCO/Drugs Rules)."
    
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
