"""
Barcode & QR code scanning service.
Uses a multi-engine pipeline:
1. OpenCV Hardware-Accelerated BarcodeDetector (EAN-13, UPC-A, Code 128, etc.)
2. OpenCV QRCodeDetector
3. PyZbar with contrast enhancement and multi-orientation rotation
4. Optical OCR GTIN-13 / EAN-13 checksum-verified fallback
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Union

import cv2
import numpy as np
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol

logger = logging.getLogger(__name__)

# Supported PyZbar barcode types for packaged commodities
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


def verify_ean13_checksum(code: str) -> bool:
    """Verify standard EAN-13 / GTIN-13 modulo-10 check digit."""
    if len(code) != 13 or not code.isdigit():
        return False
    s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(code[:12]))
    chk = (10 - (s % 10)) % 10
    return chk == int(code[12])


def get_gtin_country(code: str) -> str:
    """Identify GS1 prefix issuing country for packaged commodities."""
    if not code or len(code) < 3:
        return "Unknown"
    prefix = code[:3]
    if prefix.startswith("890"):
        return "India (GS1 India)"
    try:
        p_int = int(prefix)
        if 0 <= p_int <= 139:
            return "US / Canada"
        if 400 <= p_int <= 440:
            return "Germany"
        if 500 <= p_int <= 509:
            return "United Kingdom"
        if 690 <= p_int <= 699:
            return "China"
        if 800 <= p_int <= 839:
            return "Italy"
        if 840 <= p_int <= 849:
            return "Spain"
    except ValueError:
        pass
    return "International (GS1)"


def _unrotate_box(box_pts: List[List[float]], angle: int, orig_w: int, orig_h: int) -> List[List[int]]:
    """Transform points from rotated coordinates back to original image space."""
    if not angle or angle == 0:
        return [[int(round(p[0])), int(round(p[1]))] for p in box_pts]
    unrot = []
    for p in box_pts:
        rx, ry = p[0], p[1]
        if angle == 90:
            unrot.append([int(round(ry)), int(round(orig_h - 1 - rx))])
        elif angle == 180:
            unrot.append([int(round(orig_w - 1 - rx)), int(round(orig_h - 1 - ry))])
        elif angle == 270:
            unrot.append([int(round(orig_w - 1 - ry)), int(round(rx))])
        else:
            unrot.append([int(round(rx)), int(round(ry))])
    return unrot


def scan_single_image(image_input: Union[str, Path, np.ndarray, Image.Image]) -> List[Dict]:
    """
    Scan a single image (path, numpy array, or PIL Image) for barcodes and QR codes.
    Evaluates original orientation and 90, 180, 270 degree rotations using OpenCV and PyZbar.
    Returns decoded data along with exact bounding box spatial coordinates in the input image's coordinate space.
    """
    results = []
    seen = set()

    orig_h, orig_w = 0, 0
    img_name = "image"
    img_cv = None

    if isinstance(image_input, np.ndarray):
        img_cv = image_input
        orig_h, orig_w = img_cv.shape[:2]
        img_name = "image_array"
    elif isinstance(image_input, Image.Image):
        pil_arr = np.array(image_input)
        img_cv = cv2.cvtColor(pil_arr, cv2.COLOR_RGB2BGR) if len(pil_arr.shape) == 3 else pil_arr
        orig_h, orig_w = img_cv.shape[:2]
        img_name = "pil_image"
    else:
        img_path_str = str(image_input)
        img_name = Path(img_path_str).name
        img_cv = cv2.imread(img_path_str)
        if img_cv is not None:
            orig_h, orig_w = img_cv.shape[:2]

    if img_cv is None or orig_w == 0 or orig_h == 0:
        return []

    # Prepare standard rotations using pure OpenCV
    rotations = [
        (0, img_cv),
        (90, cv2.rotate(img_cv, cv2.ROTATE_90_CLOCKWISE)),
        (180, cv2.rotate(img_cv, cv2.ROTATE_180)),
        (270, cv2.rotate(img_cv, cv2.ROTATE_90_COUNTERCLOCKWISE)),
    ]

    # ---------------------------------------------------------
    # 1. OpenCV Barcode & QR Code Detectors (Hardware Accelerated)
    # ---------------------------------------------------------
    try:
        bd = cv2.barcode.BarcodeDetector()
        qd = cv2.QRCodeDetector()

        for angle, rot_img in rotations:
            # 1A. Barcode
            try:
                res_b = bd.detectAndDecode(rot_img)
                if res_b and res_b[0]:
                    val = str(res_b[0]).strip()
                    if val and val not in seen:
                        seen.add(val)
                        btype = "EAN13" if len(val) == 13 and val.isdigit() else "BARCODE"
                        box_pts = []
                        rect = None
                        if res_b[1] is not None and len(res_b[1]) > 0:
                            pts_raw = np.squeeze(res_b[1])
                            if len(pts_raw.shape) == 2 and pts_raw.shape[0] >= 4:
                                box_pts = _unrotate_box(pts_raw.tolist(), angle, orig_w, orig_h)
                                xs = [p[0] for p in box_pts]
                                ys = [p[1] for p in box_pts]
                                rect = {
                                    "left": min(xs),
                                    "top": min(ys),
                                    "width": max(xs) - min(xs),
                                    "height": max(ys) - min(ys)
                                }
                        results.append({
                            "data": val,
                            "type": btype,
                            "country": get_gtin_country(val),
                            "valid_checksum": verify_ean13_checksum(val) if len(val) == 13 else None,
                            "method": f"opencv_barcode_{angle}deg",
                            "source_image": img_name,
                            "box": box_pts,
                            "rect": rect,
                        })
            except Exception as e_bd:
                logger.debug(f"OpenCV barcode detect error at {angle} deg: {e_bd}")

            # 1B. QR Code
            try:
                res_q = qd.detectAndDecode(rot_img)
                if res_q and res_q[0]:
                    val = str(res_q[0]).strip()
                    if val and val not in seen:
                        seen.add(val)
                        box_pts = []
                        rect = None
                        if res_q[1] is not None and len(res_q[1]) > 0:
                            pts_raw = np.squeeze(res_q[1])
                            if len(pts_raw.shape) == 2 and pts_raw.shape[0] >= 4:
                                box_pts = _unrotate_box(pts_raw.tolist(), angle, orig_w, orig_h)
                                xs = [p[0] for p in box_pts]
                                ys = [p[1] for p in box_pts]
                                rect = {
                                    "left": min(xs),
                                    "top": min(ys),
                                    "width": max(xs) - min(xs),
                                    "height": max(ys) - min(ys)
                                }
                        results.append({
                            "data": val,
                            "type": "QRCODE",
                            "country": "N/A",
                            "valid_checksum": None,
                            "method": f"opencv_qrcode_{angle}deg",
                            "source_image": img_name,
                            "box": box_pts,
                            "rect": rect,
                        })
            except Exception as e_qd:
                logger.debug(f"OpenCV QR detect error at {angle} deg: {e_qd}")
    except Exception as e:
        logger.warning(f"OpenCV barcode detection failed on {img_name}: {e}")

    # ---------------------------------------------------------
    # 2. PyZbar Scanner directly on numpy arrays & grayscale
    # ---------------------------------------------------------
    try:
        for angle, rot_img in rotations:
            # Try both raw color and grayscale for optimal barcode reading on glossy packages
            frames_to_try = [rot_img]
            if len(rot_img.shape) == 3:
                gray = cv2.cvtColor(rot_img, cv2.COLOR_BGR2GRAY)
                frames_to_try.append(gray)

            for frame in frames_to_try:
                try:
                    decoded = decode(frame, symbols=SUPPORTED_TYPES)
                    if not decoded:
                        decoded = decode(frame)
                except Exception:
                    decoded = []

                for obj in decoded:
                    val = obj.data.decode("utf-8", errors="replace").strip()
                    if not val or val in seen:
                        continue
                    seen.add(val)

                    box_pts = []
                    rect = None
                    if obj.polygon and len(obj.polygon) >= 4:
                        raw_pts = [[p.x, p.y] for p in obj.polygon]
                        if len(raw_pts) == 4:
                            box_pts = _unrotate_box(raw_pts, angle, orig_w, orig_h)
                        else:
                            pxs = [p[0] for p in raw_pts]
                            pys = [p[1] for p in raw_pts]
                            bx = [
                                [min(pxs), min(pys)],
                                [max(pxs), min(pys)],
                                [max(pxs), max(pys)],
                                [min(pxs), max(pys)],
                            ]
                            box_pts = _unrotate_box(bx, angle, orig_w, orig_h)
                    elif obj.rect:
                        r = obj.rect
                        bx = [
                            [r.left, r.top],
                            [r.left + r.width, r.top],
                            [r.left + r.width, r.top + r.height],
                            [r.left, r.top + r.height],
                        ]
                        box_pts = _unrotate_box(bx, angle, orig_w, orig_h)

                    if box_pts:
                        xs = [p[0] for p in box_pts]
                        ys = [p[1] for p in box_pts]
                        rect = {
                            "left": min(xs),
                            "top": min(ys),
                            "width": max(xs) - min(xs),
                            "height": max(ys) - min(ys)
                        }

                    btype = obj.type
                    if btype == "I25":
                        btype = "ITF"

                    results.append({
                        "data": val,
                        "type": btype,
                        "country": get_gtin_country(val),
                        "valid_checksum": verify_ean13_checksum(val) if len(val) == 13 else None,
                        "method": f"pyzbar_{angle}deg" if angle else "pyzbar",
                        "source_image": img_name,
                        "box": box_pts,
                        "rect": rect,
                    })
    except Exception as e:
        logger.warning(f"PyZbar barcode detection failed on {img_name}: {e}")

    return results


def extract_barcodes_from_ocr_text(ocr_text: str, source_image: str = "ocr_text") -> List[Dict]:
    """
    Fallback extractor: identifies GS1 India (890...) and standard EAN-13/14
    barcode numbers directly from OCR text blocks when camera reflections
    prevent optical line decoding.
    """
    found = []
    seen = set()

    # Match GS1 India 13-digit EAN (890xxxxxxxxxx)
    for m in re.finditer(r"\b(890\d{10})\b", ocr_text):
        val = m.group(1)
        if val not in seen:
            seen.add(val)
            found.append({
                "data": val,
                "type": "EAN13",
                "country": "India (GS1 India)",
                "valid_checksum": verify_ean13_checksum(val),
                "method": "ocr_gtin_extracted",
                "source_image": source_image,
            })

    # Match 12-digit UPC or 13-14 digit GTINs
    for m in re.finditer(r"\b(\d{12,14})\b", ocr_text):
        val = m.group(1)
        if val not in seen:
            # Avoid matching FSSAI license (14 digits starting with 100 or 200)
            if len(val) == 14 and (val.startswith("100") or val.startswith("200")):
                continue
            seen.add(val)
            found.append({
                "data": val,
                "type": f"GTIN{len(val)}",
                "country": get_gtin_country(val),
                "valid_checksum": verify_ean13_checksum(val) if len(val) == 13 else None,
                "method": "ocr_gtin_extracted",
                "source_image": source_image,
            })

    return found


def scan_multiple_images(image_paths: List[str], ocr_text: Optional[str] = None) -> Dict:
    """
    Scan multiple images for barcodes/QR codes and consolidate unique results.
    Integrates both optical scan and OCR GTIN fallback.

    Args:
        image_paths: List of absolute paths to product images.
        ocr_text: Optional raw OCR text to extract optical barcode digits from.

    Returns:
        Dict with consolidated barcode scan results.
    """
    all_results: List[Dict] = []
    scanned_data: set = set()

    for path in image_paths:
        results = scan_single_image(path)
        for r in results:
            if r["data"] not in scanned_data:
                scanned_data.add(r["data"])
                all_results.append(r)

    # If optical scanner missed a barcode, extract from OCR text
    if ocr_text:
        ocr_barcodes = extract_barcodes_from_ocr_text(ocr_text)
        for r in ocr_barcodes:
            if r["data"] not in scanned_data:
                scanned_data.add(r["data"])
                all_results.append(r)

    # Determine primary barcode and primary QR code
    primary_barcode = None
    primary_qrcode = None

    for r in all_results:
        # Prefer EAN-13 from India with valid checksum
        if not primary_barcode and r["type"] in ("EAN13", "UPCA", "GTIN13", "GTIN14", "BARCODE"):
            primary_barcode = r
        if not primary_qrcode and r["type"] == "QRCODE":
            primary_qrcode = r

    # Fallback if only one code found
    if not primary_barcode and not primary_qrcode and all_results:
        primary_barcode = all_results[0]

    unique_codes = sorted(list(scanned_data))

    return {
        "found": len(all_results) > 0,
        "count": len(all_results),
        "unique_barcodes": unique_codes,
        "primary_barcode": primary_barcode,
        "primary_qrcode": primary_qrcode,
        "all_codes": all_results,
        "barcode_data": primary_barcode["data"] if primary_barcode else None,
        "barcode_type": primary_barcode["type"] if primary_barcode else None,
        "barcode_country": primary_barcode.get("country") if primary_barcode else None,
        "qrcode_data": primary_qrcode["data"] if primary_qrcode else None,
    }
