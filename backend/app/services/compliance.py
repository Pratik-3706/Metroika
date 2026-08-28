"""
Compliance engine — validates AI-extracted label data against
Legal Metrology (Packaged Commodities) Rules, 2011.
"""

import json
import logging
from typing import Dict, List, Tuple

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


def _check_field_present(extracted: Dict, field_key: str) -> Tuple[bool, str]:
    """Check if a field is present and non-empty in extracted data."""
    value = extracted.get(field_key)
    if value is None:
        return False, "Not found on the package."
    if isinstance(value, str) and not value.strip():
        return False, "Field is empty / not readable."
    if isinstance(value, bool):
        return value, "Present." if value else "Not found."
    return True, f"Found: {value}"


def run_compliance_checks(
    extracted_data: Dict,
    barcode_results: Dict,
) -> List[Dict]:
    """
    Run all compliance checks against extracted label data.

    Args:
        extracted_data: Dict from AI vision extraction.
        barcode_results: Dict from barcode scanning service.

    Returns:
        List of compliance check result dicts.
    """
    checks: List[Dict] = []

    # -----------------------------------------------------------------------
    # 1. Mandatory declarations (Rule 6)
    # -----------------------------------------------------------------------
    for rule_id, rule in MANDATORY_DECLARATIONS.items():
        field_key = rule["field_key"]

        # Special handling for country of origin — only required if imported
        if rule_id == "R6_1_G":
            is_imported = extracted_data.get("is_imported", False)
            if not is_imported:
                checks.append(
                    {
                        "rule_id": rule_id,
                        "rule_name": rule["rule_name"],
                        "rule_reference": rule["rule_reference"],
                        "status": "not_applicable",
                        "details": "Product does not appear to be imported. Country of origin check not applicable.",
                        "evidence": None,
                        "severity": rule["severity"],
                    }
                )
                continue

        present, detail = _check_field_present(extracted_data, field_key)
        value = extracted_data.get(field_key, "")

        checks.append(
            {
                "rule_id": rule_id,
                "rule_name": rule["rule_name"],
                "rule_reference": rule["rule_reference"],
                "status": "pass" if present else "fail",
                "details": detail,
                "evidence": str(value) if value else None,
                "severity": rule["severity"],
            }
        )

    # -----------------------------------------------------------------------
    # 2. Net quantity unit validation (Rule 6(1)(c))
    # -----------------------------------------------------------------------
    net_qty = extracted_data.get("net_quantity", "")
    if net_qty:
        valid, msg = validate_net_quantity(net_qty)
        # Update the existing R6_1_C check if it passed
        for c in checks:
            if c["rule_id"] == "R6_1_C" and c["status"] == "pass":
                if not valid:
                    c["status"] = "warning"
                    c["details"] = msg
                break

    # -----------------------------------------------------------------------
    # 3. MRP format check (Rule 6(1)(e))
    # -----------------------------------------------------------------------
    mrp_text = extracted_data.get("mrp", "")
    mrp_format_ok = extracted_data.get("mrp_format_correct", False)
    mrp_tax_decl = extracted_data.get("mrp_includes_tax_declaration", False)

    if mrp_text:
        valid, msg = validate_mrp_format(mrp_text)
        # Also factor in the AI's assessment
        if mrp_format_ok and mrp_tax_decl:
            status = "pass"
            detail = f"MRP format compliant: '{mrp_text}'"
        elif valid:
            status = "pass"
            detail = msg
        else:
            status = "fail"
            detail = msg
    else:
        status = "fail"
        detail = "MRP not found on the package."

    checks.append(
        {
            "rule_id": MRP_FORMAT_RULE["rule_id"],
            "rule_name": MRP_FORMAT_RULE["rule_name"],
            "rule_reference": MRP_FORMAT_RULE["rule_reference"],
            "status": status,
            "details": detail,
            "evidence": mrp_text or None,
            "severity": MRP_FORMAT_RULE["severity"],
        }
    )

    # -----------------------------------------------------------------------
    # 4. Date format check (Rule 6(1)(d))
    # -----------------------------------------------------------------------
    date_text = extracted_data.get("manufacture_date", "")
    if date_text:
        valid, msg = validate_date_format(date_text)
        checks.append(
            {
                "rule_id": DATE_FORMAT_RULE["rule_id"],
                "rule_name": DATE_FORMAT_RULE["rule_name"],
                "rule_reference": DATE_FORMAT_RULE["rule_reference"],
                "status": "pass" if valid else "warning",
                "details": msg,
                "evidence": date_text,
                "severity": DATE_FORMAT_RULE["severity"],
            }
        )
    else:
        checks.append(
            {
                "rule_id": DATE_FORMAT_RULE["rule_id"],
                "rule_name": DATE_FORMAT_RULE["rule_name"],
                "rule_reference": DATE_FORMAT_RULE["rule_reference"],
                "status": "fail",
                "details": "Month/year of manufacture not found.",
                "evidence": None,
                "severity": DATE_FORMAT_RULE["severity"],
            }
        )

    # -----------------------------------------------------------------------
    # 5. Font size assessment (Rule 7)
    # -----------------------------------------------------------------------
    font_readable = extracted_data.get("font_appears_readable", None)
    font_assessment = extracted_data.get("font_size_assessment", "not_determinable")
    pdp_estimate = extracted_data.get("pdp_area_estimate", "not_determinable")

    if font_assessment in ("adequate",):
        font_status = "pass"
        font_detail = "Font size appears adequate for the package size."
    elif font_assessment in ("small",):
        font_status = "warning"
        font_detail = "Font size appears small; may not meet minimum height requirements."
    elif font_assessment in ("very_small",):
        font_status = "fail"
        font_detail = "Font size appears very small; likely below minimum height requirements."
    else:
        font_status = "warning"
        font_detail = "Font size could not be precisely determined from images."

    # Add PDP context
    pdp_info = ""
    if pdp_estimate and pdp_estimate != "not_determinable":
        pdp_map = {
            "under_50_cm2": "≤50 cm² → min 1mm height",
            "50_to_100_cm2": "50–100 cm² → min 2mm height",
            "100_to_500_cm2": "100–500 cm² → min 3mm height",
            "over_500_cm2": ">500 cm² → min 4mm height",
        }
        pdp_info = f" Estimated PDP: {pdp_map.get(pdp_estimate, pdp_estimate)}."

    checks.append(
        {
            "rule_id": FONT_SIZE_RULE["rule_id"],
            "rule_name": FONT_SIZE_RULE["rule_name"],
            "rule_reference": FONT_SIZE_RULE["rule_reference"],
            "status": font_status,
            "details": font_detail + pdp_info,
            "evidence": f"Assessment: {font_assessment}, Readable: {font_readable}",
            "severity": FONT_SIZE_RULE["severity"],
        }
    )

    # -----------------------------------------------------------------------
    # 6. Principal Display Panel check (Rule 8)
    # -----------------------------------------------------------------------
    decl_on_front = extracted_data.get("declarations_on_front", None)
    if decl_on_front is True:
        pdp_status = "pass"
        pdp_detail = "Mandatory declarations appear to be on the Principal Display Panel."
    elif decl_on_front is False:
        pdp_status = "warning"
        pdp_detail = (
            "Mandatory declarations may not be on the Principal Display Panel. "
            "Key declarations should be on the most visible part of the package."
        )
    else:
        pdp_status = "warning"
        pdp_detail = "Could not determine if declarations are on the Principal Display Panel."

    checks.append(
        {
            "rule_id": PDP_RULE["rule_id"],
            "rule_name": PDP_RULE["rule_name"],
            "rule_reference": PDP_RULE["rule_reference"],
            "status": pdp_status,
            "details": pdp_detail,
            "evidence": None,
            "severity": PDP_RULE["severity"],
        }
    )

    # -----------------------------------------------------------------------
    # 7. Language check (Rule 6(3))
    # -----------------------------------------------------------------------
    eng = extracted_data.get("language_english", False)
    hindi = extracted_data.get("language_hindi", False)
    if eng or hindi:
        lang_status = "pass"
        langs = []
        if eng:
            langs.append("English")
        if hindi:
            langs.append("Hindi")
        lang_detail = f"Declarations found in: {', '.join(langs)}."
    else:
        lang_status = "warning"
        lang_detail = "Could not confirm declarations are in English or Hindi."

    checks.append(
        {
            "rule_id": LANGUAGE_RULE["rule_id"],
            "rule_name": LANGUAGE_RULE["rule_name"],
            "rule_reference": LANGUAGE_RULE["rule_reference"],
            "status": lang_status,
            "details": lang_detail,
            "evidence": None,
            "severity": LANGUAGE_RULE["severity"],
        }
    )

    # -----------------------------------------------------------------------
    # 8. Barcode and QR Code check (best practice/new rules)
    # ---------------------------------------------------------
    bc_data = barcode_results.get("barcode_data")
    bc_type = barcode_results.get("barcode_type")
    qr_data = barcode_results.get("qrcode_data")
    
    barcode_vis = extracted_data.get("barcode_visible", False)

    bc_status = "pass"
    details_parts = []
    
    if bc_data:
        details_parts.append(f"Barcode detected: {bc_type} — {bc_data}")
    elif barcode_vis:
        details_parts.append("Barcode visible on package but could not be decoded.")
    else:
        details_parts.append("No GTIN/EAN/UPC barcode detected.")
        bc_status = "warning"
        
    if qr_data:
        details_parts.append(f"QR Code detected — {qr_data}")
    else:
        details_parts.append("No QR Code detected.")
        bc_status = "warning"

    if bc_data and qr_data:
        bc_status = "pass"

    bc_detail = " | ".join(details_parts)
    evidence_text = f"Barcode: {bc_data or 'None'}, QR Code: {qr_data or 'None'}"

    checks.append(
        {
            "rule_id": BARCODE_RULE["rule_id"],
            "rule_name": BARCODE_RULE["rule_name"],
            "rule_reference": BARCODE_RULE["rule_reference"],
            "status": bc_status,
            "details": bc_detail,
            "evidence": barcode_results.get("barcode_data"),
            "severity": BARCODE_RULE["severity"],
        }
    )

    # -----------------------------------------------------------------------
    # 9. Unit sale price (Rule 6(2))
    # -----------------------------------------------------------------------
    unit_price = extracted_data.get("unit_sale_price")
    if unit_price:
        checks.append(
            {
                "rule_id": UNIT_SALE_PRICE_RULE["rule_id"],
                "rule_name": UNIT_SALE_PRICE_RULE["rule_name"],
                "rule_reference": UNIT_SALE_PRICE_RULE["rule_reference"],
                "status": "pass",
                "details": f"Unit sale price found: {unit_price}",
                "evidence": str(unit_price),
                "severity": UNIT_SALE_PRICE_RULE["severity"],
            }
        )
    else:
        checks.append(
            {
                "rule_id": UNIT_SALE_PRICE_RULE["rule_id"],
                "rule_name": UNIT_SALE_PRICE_RULE["rule_name"],
                "rule_reference": UNIT_SALE_PRICE_RULE["rule_reference"],
                "status": "warning",
                "details": "Unit sale price not found. Recommended for consumer comparison.",
                "evidence": None,
                "severity": UNIT_SALE_PRICE_RULE["severity"],
            }
        )

    return checks


def calculate_compliance_score(checks: List[Dict]) -> Dict:
    """
    Calculate overall compliance score from individual check results.

    Returns dict with score, counts, and overall status.
    """
    total = 0
    passed = 0
    failed = 0
    warnings = 0

    for c in checks:
        if c["status"] == "not_applicable":
            continue
        total += 1
        if c["status"] == "pass":
            passed += 1
        elif c["status"] == "fail":
            failed += 1
        elif c["status"] == "warning":
            warnings += 1

    score = (passed / total * 100) if total > 0 else 0

    # Determine overall status
    if failed == 0 and warnings == 0:
        status = "compliant"
    elif failed == 0:
        status = "warning"
    else:
        status = "non_compliant"

    return {
        "score": round(score, 1),
        "total": total,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "status": status,
    }
