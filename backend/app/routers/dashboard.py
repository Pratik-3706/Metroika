"""
Dashboard router — aggregated stats and recent scans.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Product, ProductImage, Analysis, ComplianceCheck, get_session
from app.models import DashboardStats, RecentScan

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_session)):
    """Get overall compliance dashboard statistics."""
    # Total products
    total_result = await db.execute(select(func.count(Product.id)))
    total = total_result.scalar() or 0

    # Status counts
    status_result = await db.execute(
        select(Product.status, func.count(Product.id)).group_by(Product.status)
    )
    status_counts = dict(status_result.all())

    compliant = status_counts.get("compliant", 0)
    non_compliant = status_counts.get("non_compliant", 0)
    pending = status_counts.get("pending", 0)
    warnings = status_counts.get("warning", 0)

    compliance_rate = (compliant / total * 100) if total > 0 else 0

    # Most common violations (failed checks)
    violation_result = await db.execute(
        select(
            ComplianceCheck.rule_name,
            ComplianceCheck.rule_reference,
            func.count(ComplianceCheck.id).label("count"),
        )
        .where(ComplianceCheck.status == "fail")
        .group_by(ComplianceCheck.rule_name, ComplianceCheck.rule_reference)
        .order_by(func.count(ComplianceCheck.id).desc())
        .limit(10)
    )
    common_violations = [
        {"rule_name": row[0], "rule_reference": row[1], "count": row[2]}
        for row in violation_result.all()
    ]

    return DashboardStats(
        total_products=total,
        compliant=compliant,
        non_compliant=non_compliant,
        pending=pending,
        warnings=warnings,
        compliance_rate=round(compliance_rate, 1),
        common_violations=common_violations,
    )


@router.get("/recent")
async def get_recent_scans(
    limit: int = 10,
    db: AsyncSession = Depends(get_session),
):
    """Get recent product scans with compliance status."""
    result = await db.execute(
        select(Product).order_by(Product.created_at.desc()).limit(limit)
    )
    products = result.scalars().all()

    recent = []
    for p in products:
        # Get image count
        img_result = await db.execute(
            select(func.count(ProductImage.id)).where(ProductImage.product_id == p.id)
        )
        img_count = img_result.scalar() or 0

        # Get latest analysis score
        analysis_result = await db.execute(
            select(Analysis.compliance_score)
            .where(Analysis.product_id == p.id)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        score = analysis_result.scalar() or 0.0

        recent.append(
            {
                "product_id": p.id,
                "product_name": p.name,
                "status": p.status,
                "compliance_score": score,
                "scanned_at": p.created_at.isoformat(),
                "image_count": img_count,
            }
        )

    return recent
