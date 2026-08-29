"""
Reports router — PDF report generation and download.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import Product, Analysis, get_session
from app.services.report_gen import generate_report
from app.services.compliance import calculate_compliance_score

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["reports"])


@router.post("/products/{product_id}/report")
async def create_report(
    product_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Generate a PDF compliance report for a product."""
    # Load product
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    # Load latest analysis
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
            status_code=404,
            detail="No analysis found. Please run analysis first.",
        )

    # Prepare data
    image_paths = [img.image_path for img in product.images]
    checks = [
        {
            "rule_id": c.rule_id,
            "rule_name": c.rule_name,
            "rule_reference": c.rule_reference,
            "status": c.status,
            "details": c.details,
            "evidence": c.evidence,
            "severity": c.severity,
        }
        for c in analysis.checks
    ]
    score_info = {
        "score": analysis.compliance_score,
        "total": analysis.total_checks,
        "passed": analysis.passed_checks,
        "failed": analysis.failed_checks,
        "warnings": analysis.warning_checks,
        "status": product.status,
    }
    extracted = json.loads(analysis.extracted_data) if analysis.extracted_data else {}

    # Parse annotated image paths if available
    annotated_paths = []
    if analysis.ocr_annotated_images:
        try:
            annotated_paths = json.loads(analysis.ocr_annotated_images)
        except (json.JSONDecodeError, TypeError):
            annotated_paths = []

    # Generate PDF
    report_path = generate_report(
        product_name=product.name or "Unknown Product",
        product_id=product_id,
        barcode_data=product.barcode_data,
        image_paths=image_paths,
        checks=checks,
        score_info=score_info,
        extracted_data=extracted,
        annotated_image_paths=annotated_paths,
    )

    # Update analysis with report path
    analysis.report_path = report_path
    await db.commit()

    filename = Path(report_path).name
    return {
        "message": "Report generated successfully.",
        "filename": filename,
        "download_url": f"/api/reports/{filename}",
    }


@router.get("/reports/{filename}")
async def download_report(filename: str):
    """Download a generated PDF report."""
    filepath = settings.report_dir / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Report not found.")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf",
    )
