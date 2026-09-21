"""Pydantic response / request schemas."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Any


# ---------------------------------------------------------------------------
# Product Schemas
# ---------------------------------------------------------------------------
class ProductImageOut(BaseModel):
    id: int
    filename: str
    image_path: str
    label: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    name: Optional[str] = None
    barcode_data: Optional[str] = None
    barcode_type: Optional[str] = None
    qrcode_data: Optional[str] = None


class ProductOut(BaseModel):
    id: int
    name: Optional[str] = None
    barcode_data: Optional[str] = None
    barcode_type: Optional[str] = None
    qrcode_data: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    images: List[ProductImageOut] = []

    class Config:
        from_attributes = True


class ProductListOut(BaseModel):
    id: int
    name: Optional[str] = None
    barcode_data: Optional[str] = None
    status: str
    created_at: datetime
    image_count: int = 0

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Compliance Schemas
# ---------------------------------------------------------------------------
class ComplianceCheckOut(BaseModel):
    id: int
    rule_id: str
    rule_name: str
    rule_reference: str
    status: str
    details: str
    evidence: Optional[str] = None
    severity: str

    class Config:
        from_attributes = True


class AnalysisOut(BaseModel):
    id: int
    product_id: int
    compliance_score: float
    total_checks: int
    passed_checks: int
    failed_checks: int
    warning_checks: int
    extracted_data: Optional[str] = None
    report_path: Optional[str] = None
    ocr_annotated_images: Optional[str] = None
    created_at: datetime
    checks: List[ComplianceCheckOut] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Dashboard Schemas
# ---------------------------------------------------------------------------
class DashboardStats(BaseModel):
    total_products: int
    compliant: int
    non_compliant: int
    pending: int
    warnings: int
    compliance_rate: float
    common_violations: List[dict]


class RecentScan(BaseModel):
    product_id: int
    product_name: Optional[str]
    status: str
    compliance_score: float
    scanned_at: datetime
    image_count: int


# ---------------------------------------------------------------------------
# Analysis Request
# ---------------------------------------------------------------------------
class AnalysisRequest(BaseModel):
    product_id: int


class AnalysisResponse(BaseModel):
    message: str
    analysis_id: int
    compliance_score: float
    status: str
    total_checks: int
    passed: int
    failed: int
    warnings: int
    is_unreadable: bool = False
    label_broken_or_cutoff: bool = False
    request_reupload: bool = False
    quality_message: Optional[str] = None
    deblur_applied: bool = False

