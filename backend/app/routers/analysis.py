"""
Analysis router — triggers the full compliance analysis pipeline.

Pipeline:
1. Barcode/QR scan
2. PaddleOCR (structured + annotated image)
3. Rule Engine (primary compliance checker)
4. AI Verifier (optional second-pass)
5. Store results
"""

import json
import logging
from typing import Optional, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import (
    Product,
    ProductImage,
    Analysis,
    ComplianceCheck,
    get_session,
)
from app.auth import require_role
from app.models import AnalysisOut, AnalysisResponse
from app.services.barcode import scan_multiple_images
from app.services.vision import evaluate_with_ai, is_ai_available
from app.services.compliance import run_compliance_checks, calculate_compliance_score
from app.services.ocr import (
    extract_raw_text_from_images,
    extract_all_structured,
    generate_all_annotated_images,
)
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/products", tags=["analysis"])


@router.post("/{product_id}/analyze", response_model=AnalysisResponse)
async def analyze_product(
    product_id: int,
    skip_ai: bool = False,
    category: str = None,
    db: AsyncSession = Depends(get_session),
):
    """
    Run the full compliance analysis pipeline on a product:
    1. Scan for barcodes/QR codes
    2. PaddleOCR — extract text with bounding boxes + generate annotated image
    3. Rule Engine — regex-based compliance checks (PRIMARY)
    4. AI Verifier — optional second-pass verification (can be disabled)
    5. Store results
    """
    # Load product with images
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    if not product.images:
        raise HTTPException(
            status_code=400, detail="No images uploaded for this product."
        )

    image_paths = [img.image_path for img in product.images]
    logger.info(f"Analyzing product {product_id} with {len(image_paths)} images")

    # Step 1: Barcode/QR scan (Optical)
    logger.info("Step 1: Scanning barcodes (Optical)...")
    barcode_results = scan_multiple_images(image_paths)

    # Step 2: PaddleOCR — structured extraction + annotated image
    logger.info("Step 2: Extracting text via PaddleOCR...")
    structured_ocr = extract_all_structured(image_paths)
    raw_text = " ".join(
        item["text"]
        for ocr_items in structured_ocr.values()
        for item in ocr_items
    )
    logger.info(f"OCR extracted {len(raw_text)} characters from {len(image_paths)} images.")

    # Consolidate barcodes with optical OCR GTIN digits fallback
    barcode_results = scan_multiple_images(image_paths, ocr_text=raw_text)

    # Update product barcode data if found
    if barcode_results.get("barcode_data"):
        product.barcode_data = barcode_results["barcode_data"]
        product.barcode_type = barcode_results["barcode_type"]
    if barcode_results.get("qrcode_data"):
        product.qrcode_data = barcode_results["qrcode_data"]

    # Generate annotated OCR images
    logger.info("Step 2b: Generating annotated OCR images...")
    annotated_paths = generate_all_annotated_images(image_paths, structured_ocr)
    logger.info(f"Generated {len(annotated_paths)} annotated images.")

    # Step 3: Rule Engine (PRIMARY compliance checker)
    logger.info(f"Step 3: Running Rule Engine (primary compliance checks) with category {category}...")
    initial_checks, detected_category = run_compliance_checks(
        raw_text, barcode_results, structured_ocr, manual_category=category, product_name=product.name
    )
    product.category = detected_category

    # Step 4: AI Verification (OPTIONAL)
    ai_used = False
    ai_corrected_fields = {}
    ai_res = {}
    if skip_ai or not is_ai_available():
        reason = "Bypass AI Verifier (Save API Credits / Fast Mode) enabled" if skip_ai else "AI not configured/disabled"
        logger.info(f"Step 4: AI Verifier ({reason})")
        checks = initial_checks
        raw_response = f"AI Skipped ({reason}). Using local Rule Engine only."
    else:
        logger.info("Step 4: Sending to AI Verifier for visual verification and correction of type & table attributes...")
        ai_res = await evaluate_with_ai(
            image_paths=image_paths,
            raw_text=raw_text,
            initial_report=initial_checks,
            detected_category=detected_category,
        )
        if isinstance(ai_res, dict):
            checks = ai_res.get("checks", initial_checks)
            new_cat = ai_res.get("corrected_category")
            if new_cat and str(new_cat).strip() and str(new_cat).strip().lower() != detected_category.lower():
                logger.info(f"AI Verifier corrected product category from '{detected_category}' to '{new_cat}'")
                detected_category = str(new_cat).strip().lower()
                product.category = detected_category
            ai_corrected_fields = ai_res.get("corrected_fields", {})
        else:
            checks = ai_res
        raw_response = f"Verified & corrected by {settings.vision_model}."
        ai_used = True

    # Step 5: Store analysis results
    logger.info("Step 5: Storing results...")

    # Save raw OCR output
    ocr_output_path = settings.upload_dir / f"ocr_product_{product_id}.txt"
    with open(ocr_output_path, "w", encoding="utf-8") as f:
        f.write(raw_text)

    # Save structured OCR JSON
    ocr_json_path = settings.upload_dir / f"ocr_structured_{product_id}.json"
    # Convert structured OCR for serialization (numpy arrays -> lists)
    serializable_ocr = {}
    for img_path, items in structured_ocr.items():
        serializable_ocr[img_path] = [
            {
                "text": item["text"],
                "confidence": item["confidence"],
                "box": [[float(p[0]), float(p[1])] for p in item["box"]],
            }
            for item in items
        ]
    with open(ocr_json_path, "w", encoding="utf-8") as f:
        json.dump(serializable_ocr, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved OCR output to {ocr_output_path}")
    logger.info(f"Saved structured OCR to {ocr_json_path}")

    # Map rule_ids to the flat keys expected by the frontend and PDF generator
    key_map = {
        "R6_1_A": "product_name",
        "R6_1_B": "manufacturer_name",
        "R6_1_C": "net_quantity",
        "R6_1_D": "manufacture_date",
        "R6_1_E": "mrp",
        "R6_1_H": "consumer_care",
        "FSSAI_1": "fssai_license",
        "BB_1": "expiry_date",
        "BATCH_1": "batch_number",
        "ING_1": "ingredients",
        "ALLRG_1": "allergens",
        "BARCODE": "barcode",
        "NUT_1": "nutritional_info",
        "STOR_1": "storage_instructions",
        "COO_1": "country_of_origin",
        "VEG_1": "veg_nonveg",
        "MFG_LIC": "mfg_license",
        "DRUG_LIC": "drug_license",
        "COMP_1": "composition",
        "DOSE_1": "dosage",
        "WARN_1": "warnings",
        "SCHED_1": "schedule_classification",
        "R6_UNIT": "unit_sale_price",
        "R6_LANG": "language",
    }

    pseudo_extracted_data = {"detected_category": detected_category}
    for c in checks:
        if c["rule_id"] in key_map:
            key = key_map[c["rule_id"]]
            if c["status"] == "not_applicable":
                # If there's evidence anyway (e.g. MRP on medicine), show it. Otherwise N/A.
                pseudo_extracted_data[key] = c.get("evidence") if c.get("evidence") else "N/A"
            else:
                pseudo_extracted_data[key] = c.get("evidence")

    # Apply any AI-corrected fields into pseudo_extracted_data and synchronize with checks
    reverse_key_map = {v: k for k, v in key_map.items()}
    for field_name, field_val in ai_corrected_fields.items():
        if field_val is not None and str(field_val).strip() != "" and str(field_val).strip().lower() not in ("none", "null"):
            val_str = str(field_val).strip()
            pseudo_extracted_data[field_name] = val_str
            # Also update check evidence and mark status as pass
            target_rule_id = reverse_key_map.get(field_name)
            if target_rule_id:
                for c in checks:
                    if c["rule_id"] == target_rule_id:
                        c["evidence"] = val_str
                        c["status"] = "pass"
                        c["details"] = f"Declared: {val_str} (Verified & corrected by AI Vision Verifier)"

    # Apply any explicit pass_rules from AI evaluator
    ai_pass_rules = ai_res.get("pass_rules", []) if isinstance(ai_res, dict) else []
    for c in checks:
        if c["rule_id"] in ai_pass_rules:
            c["status"] = "pass"
            if "Verified" not in c.get("details", ""):
                c["details"] = f"{c.get('details', '')} (Verified compliant by AI Vision Verifier)"

    # Synchronize dependent format checks
    if any(c["rule_id"] == "R6_1_E" and c["status"] == "pass" for c in checks):
        for c in checks:
            if c["rule_id"] == "MRP_FMT":
                c["status"] = "pass"
                c["details"] = "MRP format verified compliant."
    if any(c["rule_id"] in ("R6_1_D", "BB_1") and c["status"] == "pass" for c in checks):
        for c in checks:
            if c["rule_id"] == "DATE_FMT":
                c["status"] = "pass"
                c["details"] = "Date format verified compliant."

    # If AI is enabled and identified a product name, update product.name; otherwise default to N/A if unnamed
    ai_prod_name = ai_corrected_fields.get("product_name")
    if ai_prod_name and str(ai_prod_name).strip() and str(ai_prod_name).strip().lower() not in ("n/a", "none", "null", "unnamed product"):
        product.name = str(ai_prod_name).strip()
    elif not product.name or product.name.strip().lower() in ("unnamed product", "unknown product", ""):
        product.name = "N/A"

    # Synchronize pseudo_extracted_data product_name
    if not pseudo_extracted_data.get("product_name") or pseudo_extracted_data["product_name"] in (None, "Unnamed Product", "Unknown Product"):
        pseudo_extracted_data["product_name"] = product.name or "N/A"

    # Recalculate score after AI corrections
    score_info = calculate_compliance_score(checks)

    # Store annotated image paths
    annotated_paths_str = json.dumps(annotated_paths) if annotated_paths else None

    analysis = Analysis(
        product_id=product_id,
        ai_raw_response=raw_response,
        extracted_data=json.dumps(pseudo_extracted_data),
        compliance_score=score_info["score"],
        total_checks=score_info["total"],
        passed_checks=score_info["passed"],
        failed_checks=score_info["failed"],
        warning_checks=score_info["warnings"],
        ocr_annotated_images=annotated_paths_str,
    )
    db.add(analysis)
    await db.flush()

    # Store individual checks
    for c in checks:
        check = ComplianceCheck(
            analysis_id=analysis.id,
            rule_id=c["rule_id"],
            rule_name=c["rule_name"],
            rule_reference=c["rule_reference"],
            status=c["status"],
            details=c["details"],
            evidence=c.get("evidence"),
            severity=c["severity"],
        )
        db.add(check)

    # Update product status
    product.status = score_info["status"]
    await db.commit()

    logger.info(
        f"Analysis complete: score={score_info['score']}%, status={score_info['status']}, "
        f"ai_used={ai_used}"
    )

    return AnalysisResponse(
        message="Analysis complete",
        analysis_id=analysis.id,
        compliance_score=score_info["score"],
        status=score_info["status"],
        total_checks=score_info["total"],
        passed=score_info["passed"],
        failed=score_info["failed"],
        warnings=score_info["warnings"],
    )


@router.get("/{product_id}/analysis", response_model=AnalysisOut)
async def get_analysis(
    product_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Get the latest analysis for a product."""
    result = await db.execute(
        select(Analysis)
        .options(selectinload(Analysis.checks))
        .where(Analysis.product_id == product_id)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(
            status_code=404, detail="No analysis found for this product."
        )
    return analysis


@router.post("/clear_cache", dependencies=[Depends(require_role(["inspector"]))])
async def clear_cache():
    """Clear all cached images, txt, and json files in the uploads folder and PDF reports."""
    import os
    import shutil
    
    deleted_files = 0
    
    # Clear uploads dir (including subdirectories for generated files)
    for ext in ["*.txt", "*.json", "*_ocr_annotated.jpg", "*_ocr_annotated.jpeg", "*_ocr_annotated.png"]:
        for file_path in settings.upload_dir.rglob(ext):
            try:
                os.remove(file_path)
                deleted_files += 1
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                
    # Clear reports dir
    for file_path in settings.report_dir.rglob("*.pdf"):
        try:
            os.remove(file_path)
            deleted_files += 1
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            
    return {"message": f"Successfully deleted {deleted_files} cached files.", "deleted_files": deleted_files}


@router.post("/factory_reset", dependencies=[Depends(require_role(["inspector"]))])
async def factory_reset():
    """Wipes all files in uploads and reports directories, and drops/recreates all DB tables."""
    import os
    import shutil
    from app.database import engine, Base
    
    # 1. Clear directories
    try:
        # Clear uploads
        for item in settings.upload_dir.iterdir():
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                os.remove(item)
                
        # Clear reports
        for item in settings.report_dir.iterdir():
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                os.remove(item)
    except Exception as e:
        logger.error(f"Failed to clear directories during factory reset: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear directories.")
        
    # 2. Reset Database (Drop and Create)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset database.")
        
    return {"message": "Factory reset complete. Database and files have been wiped."}


class ListingAuditRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    mrp: Optional[str] = ""
    net_quantity: Optional[str] = ""
    country_of_origin: Optional[str] = ""
    manufacturer: Optional[str] = ""
    consumer_care: Optional[str] = ""
    category: Optional[str] = "general"


@router.post("/audit_listing")
async def audit_ecommerce_listing(req: ListingAuditRequest):
    """
    Audit an e-commerce product listing under Rule 6(10) of Legal Metrology Rules.
    Verifies that the digital listing carries mandatory declarations.
    """
    combined_parts = [
        f"Product Name: {req.title}",
        f"Description: {req.description}" if req.description else "",
        f"MRP: {req.mrp}" if req.mrp else "",
        f"Net Quantity: {req.net_quantity}" if req.net_quantity else "",
        f"Country of Origin: {req.country_of_origin}" if req.country_of_origin else "",
        f"Manufacturer: {req.manufacturer}" if req.manufacturer else "",
        f"Consumer Care: {req.consumer_care}" if req.consumer_care else "",
    ]
    raw_text = "\n".join([p for p in combined_parts if p])

    dummy_barcode = {"barcode_data": None, "barcode_type": None, "qrcode_data": None}
    checks, detected_cat = run_compliance_checks(
        raw_text=raw_text,
        barcode_results=dummy_barcode,
        structured_ocr=None,
        manual_category=req.category,
        product_name=req.title,
    )
    score_info = calculate_compliance_score(checks)

    return {
        "title": req.title,
        "compliance_score": score_info["score"],
        "status": score_info["status"],
        "total_checks": score_info["total"],
        "passed": score_info["passed"],
        "failed": score_info["failed"],
        "warnings": score_info["warnings"],
        "checks": checks,
    }

