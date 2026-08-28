"""
Barcode & QR code scanning service using pyzbar.
Decodes barcodes (EAN-13, UPC-A, Code 128, etc.) and QR codes from images.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol

logger = logging.getLogger(__name__)

# Supported barcode types for packaged commodities
SUPPORTED_TYPES = [
    ZBarSymbol.EAN13,
    ZBarSymbol.EAN8,
    ZBarSymbol.UPCA,
    ZBarSymbol.UPCE,
    ZBarSymbol.CODE128,
    ZBarSymbol.CODE39,
    ZBarSymbol.QRCODE,
    ZBarSymbol.DATABAR,
    ZBarSymbol.DATABAR_EXP,
    ZBarSymbol.I25,  # Interleaved 2 of 5
]


def scan_single_image(image_path: str) -> List[Dict]:
    """
    Scan a single image for barcodes and QR codes.

    Args:
        image_path: Absolute path to the image file.

    Returns:
        List of dicts with decoded barcode/QR data.
    """
    results = []
    try:
        img = Image.open(image_path)

        # Try with specific barcode types first
        decoded = decode(img, symbols=SUPPORTED_TYPES)

        # If nothing found, try without type filter
        if not decoded:
            decoded = decode(img)

        for obj in decoded:
            data = obj.data.decode("utf-8", errors="replace")
            rect = obj.rect
            polygon = [(p.x, p.y) for p in obj.polygon] if obj.polygon else []

            results.append(
                {
                    "data": data,
                    "type": obj.type,
                    "quality": getattr(obj, "quality", None),
                    "rect": {
                        "left": rect.left,
                        "top": rect.top,
                        "width": rect.width,
                        "height": rect.height,
                    },
                    "polygon": polygon,
                    "source_image": Path(image_path).name,
                }
            )

    except Exception as e:
        logger.warning(f"Barcode scan failed for {image_path}: {e}")

    return results


def scan_multiple_images(image_paths: List[str]) -> Dict:
    """
    Scan multiple images for barcodes/QR codes and consolidate results.

    Args:
        image_paths: List of absolute paths to product images.

    Returns:
        Dict with consolidated barcode scan results.
    """
    all_results: List[Dict] = []
    scanned_data: set = set()  # Track unique barcode data to avoid duplicates

    for path in image_paths:
        results = scan_single_image(path)
        for r in results:
            if r["data"] not in scanned_data:
                scanned_data.add(r["data"])
                all_results.append(r)

    # Determine primary barcode and primary QR code
    primary_barcode = None
    primary_qrcode = None
    
    for r in all_results:
        if not primary_barcode and r["type"] in ("EAN13", "UPCA", "EAN8", "CODE128", "CODE39"):
            primary_barcode = r
        if not primary_qrcode and r["type"] == "QRCODE":
            primary_qrcode = r

    # Fallback: if we only found something else, use it as primary
    if not primary_barcode and not primary_qrcode and all_results:
        primary_barcode = all_results[0]

    return {
        "found": len(all_results) > 0,
        "count": len(all_results),
        "primary_barcode": primary_barcode,
        "primary_qrcode": primary_qrcode,
        "all_codes": all_results,
        "barcode_data": primary_barcode["data"] if primary_barcode else None,
        "barcode_type": primary_barcode["type"] if primary_barcode else None,
        "qrcode_data": primary_qrcode["data"] if primary_qrcode else None,
    }
