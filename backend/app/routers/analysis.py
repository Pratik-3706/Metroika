"""
Analysis router — triggers the full compliance analysis pipeline.
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
from app.services.vision import analyze_product_images
from app.services.compliance import run_compliance_checks, calculate_compliance_score
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/products", tags=["analysis"])


@router.post("/{product_id}/analyze", response_model=AnalysisResponse)
async def analyze_product(
    product_id: int,
    skip_ai: bool = False,
    db: AsyncSession = Depends(get_session),
):
    """
    Run the full compliance analysis pipeline on a product:
    1. Load all product images
    2. Scan for barcodes/QR codes
    3. Send images to AI vision model for label extraction (unless skip_ai=True)
    4. Run compliance engine against extracted data
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

    # Step 2: AI Vision analysis
    if skip_ai:
        logger.info("Step 2: AI Vision analysis (SKIPPED via UI toggle)...")
        extracted_data = {}
    else:
        logger.info("Step 2: Running AI vision analysis...")
        extracted_data = await analyze_product_images(image_paths)

        if "error" in extracted_data:
            logger.error(f"Vision analysis error: {extracted_data['error']}")
            # Create a minimal analysis record with the error
            analysis = Analysis(
                product_id=product_id,
                ai_raw_response=json.dumps(extracted_data),
                extracted_data=json.dumps(extracted_data),
                compliance_score=0,
                total_checks=0,
                passed_checks=0,
                failed_checks=0,
                warning_checks=0,
            )
            db.add(analysis)
            product.status = "pending"
            await db.commit()

            raise HTTPException(
                status_code=502,
                detail=f"AI vision analysis failed: {extracted_data['error']}",
            )

    # Update product name from AI extraction if not set
    if not product.name and extracted_data.get("product_name"):
        product.name = extracted_data["product_name"]

    # Step 3: Run compliance checks
    logger.info("Step 3: Running compliance checks...")
    checks = run_compliance_checks(extracted_data, barcode_results)
    score_info = calculate_compliance_score(checks)

    # Step 4: Store analysis results
    logger.info("Step 4: Storing results...")
    raw_response = extracted_data.pop("_raw_response", "")

    # Save raw OCR output to a JSON file for the user, next to the uploaded images
    ocr_output_path = settings.upload_dir / f"ocr_product_{product_id}.json"
    with open(ocr_output_path, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, indent=4, ensure_ascii=False)
    logger.info(f"Saved OCR output to {ocr_output_path}")

    analysis = Analysis(
        product_id=product_id,
        ai_raw_response=raw_response,
        extracted_data=json.dumps(extracted_data),
        compliance_score=score_info["score"],
        total_checks=score_info["total"],
        passed_checks=score_info["passed"],
        failed_checks=score_info["failed"],
        warning_checks=score_info["warnings"],
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
        f"Analysis complete: score={score_info['score']}%, status={score_info['status']}"
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
