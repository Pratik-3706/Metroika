"""
Products router — CRUD endpoints with multi-image upload support.
"""

import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import Product, ProductImage, get_session
from app.models import ProductOut, ProductListOut
from app.auth import require_role

router = APIRouter(prefix="/api/products", tags=["products"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def _validate_file(file: UploadFile) -> bool:
    """Check if file has an allowed image extension."""
    if not file.filename:
        return False
    ext = Path(file.filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


@router.post("", response_model=ProductOut)
async def create_product(
    name: Optional[str] = Form(None),
    images: List[UploadFile] = File(...),
    labels: Optional[str] = Form(None),  # Comma-separated labels: "front,back,side"
    db: AsyncSession = Depends(get_session),
):
    """
    Create a new product with multiple image uploads.
    Supports front, back, side, and additional label images.
    """
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required.")

    # Parse labels
    label_list = []
    if labels:
        label_list = [l.strip() for l in labels.split(",")]

    # Create product
    product = Product(name=name)
    db.add(product)
    await db.flush()  # Get the product ID

    # Create product-specific upload directory
    product_dir = settings.upload_dir / str(product.id)
    product_dir.mkdir(parents=True, exist_ok=True)

    # Save images
    for i, image_file in enumerate(images):
        if not _validate_file(image_file):
            continue

        # Generate unique filename
        ext = Path(image_file.filename).suffix.lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = product_dir / unique_name

        # Save file (applying EXIF rotation so OpenCV doesn't get confused)
        from PIL import Image, ImageOps
        import io
        
        content = await image_file.read()
        try:
            with Image.open(io.BytesIO(content)) as img:
                # Convert RGBA to RGB for saving if necessary, though keep format if possible
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                # Apply EXIF rotation to actual pixels and strip EXIF
                img = ImageOps.exif_transpose(img)
                img.save(file_path, format=img.format or "JPEG")
        except Exception as e:
            # Fallback to saving raw bytes if Pillow fails for some reason
            with open(file_path, "wb") as f:
                f.write(content)

        # Determine label
        label = label_list[i] if i < len(label_list) else f"image_{i + 1}"

        # Create DB record
        img_record = ProductImage(
            product_id=product.id,
            filename=image_file.filename,
            image_path=str(file_path),
            label=label,
        )
        db.add(img_record)

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Product).options(selectinload(Product.images)).where(Product.id == product.id)
    )
    product = result.scalar_one()
    return product


@router.get("", response_model=List[ProductListOut])
async def list_products(
    search: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_session),
):
    """List all products with optional search and status filter."""
    query = select(Product).order_by(Product.created_at.desc())

    if search:
        query = query.where(
            Product.name.ilike(f"%{search}%")
            | Product.barcode_data.ilike(f"%{search}%")
        )
    if status:
        query = query.where(Product.status == status)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    products = result.scalars().all()

    # Get image counts
    out = []
    for p in products:
        count_result = await db.execute(
            select(func.count(ProductImage.id)).where(ProductImage.product_id == p.id)
        )
        img_count = count_result.scalar() or 0
        out.append(
            ProductListOut(
                id=p.id,
                name=p.name,
                barcode_data=p.barcode_data,
                status=p.status,
                created_at=p.created_at,
                image_count=img_count,
            )
        )
    return out


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Get product details with all images."""
    result = await db.execute(
        select(Product).options(selectinload(Product.images)).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_session),
    inspector = Depends(require_role(["inspector"])),
):
    """Delete a product and all associated data (Inspector Only)."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    # Delete uploaded files
    product_dir = settings.upload_dir / str(product_id)
    if product_dir.exists():
        shutil.rmtree(product_dir)

    await db.delete(product)
    await db.commit()
    return {"message": f"Product {product_id} deleted successfully."}
