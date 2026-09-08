"""Database models and engine setup using SQLAlchemy async."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, Enum as SAEnum
from datetime import datetime
from typing import Optional, List
import enum

from app.config import settings


# ---------------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------------
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ComplianceStatus(str, enum.Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING = "pending"
    WARNING = "warning"


class UserRole(str, enum.Enum):
    INSPECTOR = "inspector"
    MERCHANT = "merchant"
    PUBLIC = "public"


class CheckResult(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    salt: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(20), default=UserRole.PUBLIC.value)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    barcode_data: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    barcode_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    qrcode_data: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ComplianceStatus.PENDING.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    images: Mapped[List["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    analyses: Mapped[List["Analysis"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    filename: Mapped[str] = mapped_column(String(255))
    image_path: Mapped[str] = mapped_column(String(512))
    label: Mapped[str] = mapped_column(String(50), default="front")  # front/back/side/additional
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="images")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    ai_raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    compliance_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_checks: Mapped[int] = mapped_column(Integer, default=0)
    passed_checks: Mapped[int] = mapped_column(Integer, default=0)
    failed_checks: Mapped[int] = mapped_column(Integer, default=0)
    warning_checks: Mapped[int] = mapped_column(Integer, default=0)
    report_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ocr_annotated_images: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of paths
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="analyses")
    checks: Mapped[List["ComplianceCheck"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))
    rule_id: Mapped[str] = mapped_column(String(20))
    rule_name: Mapped[str] = mapped_column(String(255))
    rule_reference: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))  # pass/fail/warning/not_applicable
    details: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium")  # low/medium/high/critical

    analysis: Mapped["Analysis"] = relationship(back_populates="checks")


# ---------------------------------------------------------------------------
# DB Init
# ---------------------------------------------------------------------------
async def init_db():
    """Create all tables and seed default users if empty."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default accounts
    from sqlalchemy import select
    from app.auth import hash_password
    from app.config import settings

    async with async_session() as session:
        result = await session.execute(select(User).limit(1))
        if not result.scalar_one_or_none():
            
            # Read hexed passwords from settings (which loads them from .env)
            admin_pass = bytes.fromhex(settings.admin_pass_hex).decode('utf-8')
            merchant_pass = bytes.fromhex(settings.merchant_pass_hex).decode('utf-8')
            public_pass = bytes.fromhex(settings.public_pass_hex).decode('utf-8')

            defaults = [
                ("inspector", admin_pass, UserRole.INSPECTOR.value, "Legal Metrology Enforcement Officer"),
                ("merchant", merchant_pass, UserRole.MERCHANT.value, "Brand Compliance Officer"),
                ("public", public_pass, UserRole.PUBLIC.value, "Consumer User"),
            ]
            for uname, pwd, role, fname in defaults:
                p_hash, salt = hash_password(pwd)
                user = User(
                    username=uname,
                    password_hash=p_hash,
                    salt=salt,
                    role=role,
                    full_name=fname,
                )
                session.add(user)
            await session.commit()


async def get_session() -> AsyncSession:
    """Dependency for FastAPI routes."""
    async with async_session() as session:
        yield session
