"""
OCR Service — PaddleOCR (v3.7) integration as requested.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PaddleOCR Engine Initialization
# ---------------------------------------------------------------------------
HAS_OCR = False
ocr_engine = None

try:
    # Disable PIR API to prevent C++ crashes on certain CPUs
    os.environ["FLAGS_enable_pir_api"] = "0"
    # Prevent CPU thread thrashing which can cause 5+ minute hangs
    os.environ["OMP_NUM_THREADS"] = "4"
    
    from paddleocr import PaddleOCR
    import paddle
    
    # Auto-detect GPU
    use_gpu = paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
    device = "gpu" if use_gpu else "cpu"
    
    # Initialize with orientation classification enabled to fix vertical text issues
    ocr_engine = PaddleOCR(
        use_textline_orientation=True,       # Enables character/line rotation classification (keep this)
        use_doc_orientation_classify=False,   # Disable full document rotation as it incorrectly flips packaging images
        use_doc_unwarping=False,
        device=device,                       # Use GPU when available for ~5-10x speedup
        enable_mkldnn=False,                 # MUST be False to prevent PIR array attribute crash
        cpu_threads=4                        # Limit math threads to prevent the 5+ minute hang (CPU fallback)
    )
    HAS_OCR = True
    logger.info(f"PaddleOCR (v3.7) initialized successfully on {device.upper()}.")
except ImportError:
    logger.warning("PaddleOCR not installed. OCR features will be unavailable.")
except Exception as e:
    logger.error(f"PaddleOCR initialization failed: {e}")

# Global cache to store generated image paths during extraction
_ANNOTATED_CACHE = {}

# ---------------------------------------------------------------------------
# Core OCR Functions
# ---------------------------------------------------------------------------

def extract_structured_ocr(image_path: str) -> List[Dict]:
    """
    Run PaddleOCR on a single image.
    Extracts text, confidence, and bounding boxes.
    Also generates the annotated image exactly like the default PaddleOCR output.
    """
    if not HAS_OCR or not ocr_engine:
        logger.error("Cannot run OCR: PaddleOCR is not available.")
        return []

    try:
        # Run prediction on the full image
        result = ocr_engine.predict(input=image_path)
        all_detections = []
        
        # We will use a temp dir to catch the save_to_img output
        with tempfile.TemporaryDirectory() as temp_dir:
            for res in result:
                # Save the default PaddleOCR annotated image
                res.save_to_img(save_path=temp_dir)
                
                # Parse the extracted data
                texts = res.get("rec_texts", [])
                scores = res.get("rec_scores", [])
                boxes = res.get("rec_polys", [])
                
                for text, score, box in zip(texts, scores, boxes):
                    all_detections.append({
                        "text": text,
                        "confidence": float(score),
                        "box": box,
                        "source": "paddleocr"
                    })
                    
            # -----------------------------------------------------
            # Extract Barcodes and QR Codes with pyzbar
            # -----------------------------------------------------
            barcode_detections = []
            try:
                import cv2
                from pyzbar.pyzbar import decode
                
                img_cv2 = cv2.imread(image_path)
                if img_cv2 is not None:
                    decoded_objects = decode(img_cv2)
                    for obj in decoded_objects:
                        text_data = obj.data.decode("utf-8")
                        rect = obj.rect
                        box = [
                            [rect.left, rect.top],
                            [rect.left + rect.width, rect.top],
                            [rect.left + rect.width, rect.top + rect.height],
                            [rect.left, rect.top + rect.height]
                        ]
                        barcode_detections.append({
                            "text": text_data,
                            "confidence": 1.0,
                            "box": box,
                            "source": "pyzbar"
                        })
                    all_detections.extend(barcode_detections)
            except ImportError as e:
                logger.warning(f"Barcode scanning skipped: pyzbar failed to load (likely missing Visual C++ Redistributable on Windows or libzbar0 on Linux): {e}")
            except Exception as e:
                logger.warning(f"Barcode scanning failed: {e}")
                    
            # Find the saved image in the temp dir and move it to our final destination
            temp_files = os.listdir(temp_dir)
            if temp_files:
                # Assume there is only one image output from the prediction
                saved_img = temp_files[0]
                temp_img_path = os.path.join(temp_dir, saved_img)
                
                # Define final output path
                p = Path(image_path)
                final_annotated_path = str(p.parent / f"{p.stem}_ocr_annotated{p.suffix}")
                
                # Draw barcode boxes onto the PaddleOCR generated image
                if barcode_detections:
                    paddle_img = cv2.imread(temp_img_path)
                    if paddle_img is not None:
                        for b in barcode_detections:
                            pts = b["box"]
                            # Draw a green bounding box around the barcode/QR code
                            cv2.rectangle(paddle_img, (pts[0][0], pts[0][1]), (pts[2][0], pts[2][1]), (0, 255, 0), 2)
                            cv2.putText(paddle_img, b["text"], (pts[0][0], pts[0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        cv2.imwrite(temp_img_path, paddle_img)
                
                shutil.move(temp_img_path, final_annotated_path)
                _ANNOTATED_CACHE[image_path] = final_annotated_path
                logger.info(f"Saved PaddleOCR annotated image to {final_annotated_path}")

        # Filter by confidence threshold
        filtered = [d for d in all_detections if d["confidence"] >= settings.ocr_confidence_threshold]

        logger.info(f"OCR on {Path(image_path).name}: {len(all_detections)} raw -> {len(filtered)} final")
        return filtered

    except Exception as e:
        logger.error(f"OCR failed on {image_path}: {e}")
        return []


def extract_raw_text_from_images(image_paths: List[str]) -> str:
    """Backward-compatible interface for the rule engine."""
    if not HAS_OCR or not ocr_engine:
        return ""
    all_text = []
    for img_path in image_paths:
        structured = extract_structured_ocr(img_path)
        for item in structured:
            all_text.append(item["text"])
    return " ".join(all_text)


def extract_all_structured(image_paths: List[str]) -> Dict[str, List[Dict]]:
    results = {}
    for img_path in image_paths:
        results[img_path] = extract_structured_ocr(img_path)
    return results


# ---------------------------------------------------------------------------
# Annotated Image Generation
# ---------------------------------------------------------------------------

def generate_annotated_image(image_path: str, ocr_results: List[Dict], output_path: Optional[str] = None) -> Optional[str]:
    """
    Returns the path to the annotated image generated during extract_structured_ocr.
    """
    if not ocr_results:
        return None
        
    cached_path = _ANNOTATED_CACHE.get(image_path)
    if cached_path and os.path.exists(cached_path):
        if output_path and output_path != cached_path:
            shutil.copy(cached_path, output_path)
            return output_path
        return cached_path
    
    return None

def generate_all_annotated_images(image_paths: List[str], all_ocr_results: Dict[str, List[Dict]]) -> List[str]:
    annotated_paths = []
    for img_path in image_paths:
        ocr_results = all_ocr_results.get(img_path, [])
        if ocr_results:
            annotated_path = generate_annotated_image(img_path, ocr_results)
            if annotated_path:
                annotated_paths.append(annotated_path)
    return annotated_paths
