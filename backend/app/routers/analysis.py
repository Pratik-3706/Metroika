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

from fastapi import APIRouter, Depends, HTTPException
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

    # Step 1: Barcode/QR scan
    logger.info("Step 1: Scanning barcodes...")
    barcode_results = scan_multiple_images(image_paths)

    # Update product barcode data if found
    if barcode_results.get("barcode_data"):
        product.barcode_data = barcode_results["barcode_data"]
        product.barcode_type = barcode_results["barcode_type"]
    if barcode_results.get("qrcode_data"):
        product.qrcode_data = barcode_results["qrcode_data"]

    # Step 2: PaddleOCR — structured extraction + annotated image
    logger.info("Step 2: Extracting text via PaddleOCR...")
    structured_ocr = extract_all_structured(image_paths)
    raw_text = " ".join(
        item["text"]
        for ocr_items in structured_ocr.values()
        for item in ocr_items
    )
    logger.info(f"OCR extracted {len(raw_text)} characters from {len(image_paths)} images.")

    # Generate annotated OCR images
    logger.info("Step 2b: Generating annotated OCR images...")
    annotated_paths = generate_all_annotated_images(image_paths, structured_ocr)
    logger.info(f"Generated {len(annotated_paths)} annotated images.")

    # Step 3: Rule Engine (PRIMARY compliance checker)
    logger.info(f"Step 3: Running Rule Engine (primary compliance checks) with category {category}...")
    initial_checks, detected_category = run_compliance_checks(
        raw_text, barcode_results, structured_ocr, manual_category=category
    )
    product.category = detected_category

    # Step 4: AI Verification (OPTIONAL)
    ai_used = False
    if skip_ai or not is_ai_available():
        reason = "skipped via UI toggle" if skip_ai else "AI not configured/disabled"
        logger.info(f"Step 4: AI Verifier ({reason})")
        checks = initial_checks
        raw_response = f"AI Skipped ({reason}). Using local Rule Engine only."
    else:
        logger.info("Step 4: Sending to AI Verifier for second-pass...")
        checks = await evaluate_with_ai(image_paths, raw_text, initial_checks)
        raw_response = f"Verified by {settings.vision_model}."
        ai_used = True

    score_info = calculate_compliance_score(checks)

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
        "BARCODE": "barcode"
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


@router.post("/clear_cache")
async def clear_cache():
    """Clear all cached images, txt, and json files in the uploads folder and PDF reports."""
    import os
    import shutil
    
    deleted_files = 0
    
    # Clear uploads dir
    for ext in ["*.txt", "*.json", "*_ocr_annotated.jpg", "*_ocr_annotated.jpeg", "*_ocr_annotated.png"]:
        for file_path in settings.upload_dir.glob(ext):
            try:
                os.remove(file_path)
                deleted_files += 1
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                
    # Clear reports dir
    for file_path in settings.report_dir.glob("*.pdf"):
        try:
            os.remove(file_path)
            deleted_files += 1
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            
    return {"message": f"Successfully deleted {deleted_files} cached files.", "deleted_files": deleted_files}

