import csv
import io
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import Product, Analysis, get_session
from app.auth import require_role
from app.rules.metrology import get_statutory_penalty
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


@router.get("/products/{product_id}/report/csv")
async def download_report_csv(
    product_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Export compliance inspection report as an editable CSV format."""
    # Load product
    result = await db.execute(
        select(Product).where(Product.id == product_id)
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
        raise HTTPException(status_code=404, detail="No analysis found for this product.")

    output = io.StringIO()
    writer = csv.writer(output)

    # Header metadata
    writer.writerow(["METROIKA LEGAL METROLOGY COMPLIANCE REPORT"])
    writer.writerow(["Product ID", product.id])
    writer.writerow(["Product Name", product.name or "Unnamed Product"])
    writer.writerow(["Barcode", product.barcode_data or "N/A"])
    writer.writerow(["Category", product.category or "General"])
    writer.writerow(["Compliance Score", f"{analysis.compliance_score:.1f}%"])
    writer.writerow(["Overall Status", product.status.upper()])
    writer.writerow(["Inspection Date", analysis.created_at.strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])

    # Table headers
    writer.writerow([
        "Rule ID",
        "Rule Name",
        "Statutory Reference",
        "Compliance Status",
        "Severity",
        "Evidence Found",
        "Findings / Details",
        "Statutory Penal Provision",
    ])

    for c in analysis.checks:
        penalty = get_statutory_penalty(c.rule_id)
        pen_str = f"{penalty['section']} ({penalty['first_offence']})" if penalty and c.status in ("fail", "warning") else ""
        writer.writerow([
            c.rule_id,
            c.rule_name,
            c.rule_reference,
            c.status.upper(),
            c.severity.upper(),
            c.evidence or "",
            c.details or "",
            pen_str,
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=compliance_report_{product_id}.csv"},
    )


@router.get("/products/{product_id}/report/notice")
async def generate_show_cause_notice(
    product_id: int,
    db: AsyncSession = Depends(get_session),
    inspector = Depends(require_role(["inspector"])),
):
    """
    Generate an official Statutory Show Cause Notice under Section 36 of
    the Legal Metrology Act, 2009 for detected non-compliances (Inspector Only).
    """
    # Load product
    result = await db.execute(
        select(Product).where(Product.id == product_id)
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
        raise HTTPException(status_code=404, detail="No analysis found for this product.")

    extracted = json.loads(analysis.extracted_data) if analysis.extracted_data else {}
    mfr_name = extracted.get("manufacturer_name") or product.name or "Concerned Manufacturer/Packer"

    failed_checks = [c for c in analysis.checks if c.status == "fail"]
    warning_checks = [c for c in analysis.checks if c.status == "warning"]

    violations_list = []
    for c in failed_checks:
        penalty = get_statutory_penalty(c.rule_id)
        violations_list.append({
            "rule": f"{c.rule_name} ({c.rule_reference})",
            "finding": c.details,
            "statutory_provision": penalty["section"] if penalty else "Legal Metrology Act, 2009",
            "statutory_penalty": penalty["first_offence"] if penalty else "As prescribed by law",
        })

    notice_number = f"LM/INSP/{datetime.now().year}/{product.id:04d}"
    
    return {
        "notice_number": notice_number,
        "date_of_issue": datetime.now().strftime("%d-%B-%Y"),
        "product_id": product.id,
        "product_name": product.name or "Packaged Commodity",
        "barcode": product.barcode_data,
        "recipient_name": mfr_name,
        "inspector_name": inspector.full_name or inspector.username,
        "inspector_designation": "Legal Metrology Enforcement Officer",
        "total_violations": len(failed_checks),
        "violations": violations_list,
        "warnings": [f"{c.rule_name}: {c.details}" for c in warning_checks],
        "statutory_sections_cited": list(set([v["statutory_provision"] for v in violations_list])),
        "maximum_penalty_exposure": "Fine up to ₹25,000 for 1st offence; ₹50,000 for 2nd offence (Section 36)",
        "compliance_deadline_days": 15,
    }


@router.get("/reports/{filename}")
async def download_report(filename: str):
    """Download a generated PDF report with path traversal defense."""
    # Defensive check against directory traversal attacks
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename: Path traversal characters are not permitted.",
        )

    filepath = settings.report_dir / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Report not found.")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf",
    )
