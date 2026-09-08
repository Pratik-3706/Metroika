"""
Vision service — OPTIONAL AI verifier using the Kimi K2.5 vision model.

This is NOT the core compliance engine. The local OCR + Rule Engine handles
all compliance checks independently. The AI verifier only acts as a
second-pass to catch things the rule engine might have missed.

Can be completely disabled via config (ai_enabled=False) or per-request
(skip_ai=True).
"""

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# System prompt that instructs the vision model how to act as an evaluator and data corrector
EVALUATOR_SYSTEM_PROMPT = """You are an expert Legal Metrology & Packaged Commodity compliance AI Vision Evaluator.
A local OCR rule engine has scanned product packaging images and generated an initial compliance extraction.

Your task is to review the physical packaging images and perform strict visual verification:
1. Identify the PRODUCT NAME: The brand name and/or generic commodity/medicine formulation name (e.g. 'Kissan Fresh Tomato Ketchup' or 'Sodium Hyaluronate BP 0.1% Eye Drops'). If no standalone brand logo is visible on the captured panels, use the active formulation / generic product title from the package. Do NOT leave product_name null or N/A if the product name or formulation is visible.
2. Verify the product category (must be one of: 'food', 'medicine', 'cosmetic', 'electronics', 'general').
3. Visually read and extract every declaration printed on the packaging:
   - product_name: Exact brand and generic name (e.g. "Kissan Fresh Tomato Ketchup")
   - net_quantity: Declared net weight / volume / units (e.g. "1.1 kg", "500 g", "10 Tablets")
   - mrp: Exact Maximum Retail Price with currency and taxes (e.g. "₹ 140.00 (Inclusive of all Taxes)").
     *** CRITICAL INSTRUCTION FOR MRP ***:
     - On Indian packaging, labels frequently state "FOR MRP, USP, PKD, USE BY & BATCH NO. PLEASE SEE BOTTOM OF PACK" (or "SEE CAP", "SEE CRIMP", "SEE REVERSE").
     - NEVER return placeholder phrases like "See bottom of pack", "Please see bottom", or "See cap" as the value of 'mrp'!
     - When multiple images are provided, you MUST inspect the close-up images of the container bottom, cap, neck, crimp, or stamped area for the actual printed or inkjet/dot-matrix price.
     - Look for stamped prices such as "₹140/-", "Rs. 140", "140.00".
     - If there is a promotional strike-through / crossed-out price next to an offer price (e.g. "~₹160/-~ ₹140/-"), ALWAYS extract the final active selling price: "₹ 140.00 (Inclusive of all Taxes)".
     - You can cross-verify against Unit Sale Price (USP) and Net Quantity (e.g. 127.27/kg * 1.1kg = ₹140).
   - manufacture_date: Actual stamped date of manufacture/packaging (e.g. "03/04/26"). Do not output "See bottom of pack".
   - expiry_date: Actual stamped expiry date / best before / use by date (e.g. "02/01/27"). Do not output "See bottom of pack".
   - batch_number: Actual stamped lot or batch code (e.g. "D1355 L2-1"). Do not output "See bottom of pack".
   - manufacturer_name: Complete name and address of manufacturer/packer
   - consumer_care: Consumer care contact details (phone, email, address, or QR code)
   - country_of_origin: Country of origin (e.g. "India")
   - fssai_license: 14-digit FSSAI number (if food)
   - veg_nonveg: "Veg" or "Non-Veg" (if food logo present)
   - composition: Formulation or active ingredients (if medicine/cosmetic)
   - dosage: Dosage instructions (if medicine)
   - warnings: Warnings, precautions, or caution statements
   - storage_instructions: Storage conditions (e.g. "Store below 30°C")
   - mfg_license: Drug / manufacturing license number (e.g. "51/UA/SC/P-2013")
4. In "pass_rules", list any rule IDs that are visually present and compliant on the packaging (e.g. "R6_1_A", "R6_1_B", "R6_1_C", "R6_1_D", "R6_1_E", "MRP_FMT", "DATE_FMT", "BB_1", "BATCH_1", "BARCODE", "MFG_LIC", "DRUG_LIC", "COMP_1", "DOSE_1", "WARN_1", "STOR_1", "COO_1").

Return ONLY a valid JSON object matching this schema:
{
  "corrected_category": "<food|medicine|cosmetic|electronics|general or null>",
  "pass_rules": ["<rule_id>", ...],
  "corrected_fields": {
    "product_name": "<exact text on image or null>",
    "net_quantity": "<exact text on image or null>",
    "mrp": "<exact text on image or null>",
    "manufacture_date": "<exact text on image or null>",
    "expiry_date": "<exact text on image or null>",
    "batch_number": "<exact text on image or null>",
    "manufacturer_name": "<exact text on image or null>",
    "consumer_care": "<exact text on image or null>",
    "country_of_origin": "<exact text on image or null>",
    "fssai_license": "<exact text on image or null>",
    "veg_nonveg": "<Veg | Non-Veg or null>",
    "composition": "<exact text on image or null>",
    "dosage": "<exact text on image or null>",
    "warnings": "<exact text on image or null>",
    "storage_instructions": "<exact text on image or null>",
    "mfg_license": "<exact text on image or null>"
  }
}
Do not include markdown codeblocks or conversational text. Return only valid JSON.
"""


def is_ai_available() -> bool:
    """Check if AI evaluation is available and enabled."""
    if not settings.ai_enabled:
        return False
    if settings.aicredits_api_key in ("YOUR_API_KEY", "", None):
        return False
    return True


def _encode_image(image_path: str) -> str:
    """Read an image file, resize if too large, and return its base64-encoded JPEG string."""
    from PIL import Image
    import io
    
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "P", "LA", "L"):
            img = img.convert("RGB")
            
        max_dim = 1024
        if max(img.width, img.height) > max_dim:
            ratio = max_dim / max(img.width, img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _get_mime_type(filename: str) -> str:
    """Determine MIME type from file extension."""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/jpeg")


async def evaluate_with_ai(
    image_paths: List[str],
    raw_text: str,
    initial_report: List[Dict],
    detected_category: str = "general",
) -> Dict[str, Any]:
    """
    Send concise report summary and images to the AI vision evaluator to verify
    and correct the product type/category and all metadata table attributes against
    what is printed on the physical packaging images.
    """
    if not is_ai_available():
        logger.info("AI evaluation skipped: AI is not available or disabled.")
        return {
            "checks": initial_report,
            "corrected_category": None,
            "corrected_fields": {},
            "pass_rules": [],
        }

    try:
        import openai
    except ImportError:
        logger.warning("OpenAI package not installed. AI evaluation skipped.")
        return {
            "checks": initial_report,
            "corrected_category": None,
            "corrected_fields": {},
            "pass_rules": [],
        }

    client = openai.OpenAI(
        base_url=settings.aicredits_base_url,
        api_key=settings.aicredits_api_key,
    )

    # Prepare concise summary of initial checks so prompt is token-efficient
    summary_checks = {}
    for c in initial_report:
        if c.get("evidence") or c.get("status") in ("fail", "warning"):
            ev = c.get("evidence")
            # If evidence is merely a placeholder reference (e.g. 'See bottom of pack'),
            # explicitly indicate to AI that the numeric value needs visual extraction from bulk photos
            if ev and any(p in str(ev).lower() for p in ["see bottom", "see cap", "see crimp", "see reverse", "see neck", "please see"]):
                ev = f"Placeholder reference detected on label ('{ev}'). MUST visually locate and extract physical stamped value from images."
            summary_checks[c["rule_id"]] = {
                "name": c.get("rule_name"),
                "status": c.get("status"),
                "evidence": ev,
            }

    content: list = [
        {
            "type": "text",
            "text": (
                "Please visually inspect the attached product packaging images.\n\n"
                f"--- DETECTED CATEGORY BY LOCAL RULE ENGINE ---\n{detected_category}\n\n"
                f"--- INITIAL REPORT SUMMARY ---\n{json.dumps(summary_checks, indent=2)}\n\n"
                f"--- RAW OCR TEXT SNIPPET ---\n{raw_text[:1500]}\n\n"
                "Verify every attribute against the images. If any declaration was missed or incorrect in the initial report, "
                "supply the true values in 'corrected_fields' and include all compliant rules in 'pass_rules'. Return the final JSON."
            ),
        }
    ]

    for img_path in image_paths:
        try:
            b64 = _encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        except Exception as e:
            logger.warning(f"Could not encode image {img_path}: {e}")

    if len(content) < 2:
        logger.error("No images could be loaded for evaluation.")
        return {
            "checks": initial_report,
            "corrected_category": None,
            "corrected_fields": {},
            "pass_rules": [],
        }

    try:
        model_name = (settings.vision_model or "google/gemini-2.5-flash").strip()
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=8192,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content or ""
        raw_content = raw_content.strip()

        # Clean JSON markdown fences
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
            raw_content = raw_content.split("```")[1].strip()
            if raw_content.startswith("json"):
                raw_content = raw_content[4:].strip()

        # Extract outer JSON block
        start_idx = raw_content.find('{')
        end_idx = raw_content.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = raw_content[start_idx:end_idx+1]
        else:
            json_str = raw_content

        parsed = None
        try:
            parsed = json.loads(json_str)
        except Exception as json_err:
            logger.warning(f"Standard json.loads failed: {json_err}. Attempting partial recovery...")
            repaired_str = json_str.strip()
            if repaired_str.count('"') % 2 != 0:
                repaired_str += '"'
            open_braces = repaired_str.count('{') - repaired_str.count('}')
            if open_braces > 0:
                repaired_str += '}' * open_braces
            try:
                parsed = json.loads(repaired_str)
            except Exception:
                parsed = {"corrected_fields": {}, "pass_rules": []}
                for key in ["product_name", "net_quantity", "mrp", "manufacture_date", "expiry_date", "batch_number", "manufacturer_name", "consumer_care", "country_of_origin", "composition", "dosage", "warnings", "storage_instructions", "mfg_license"]:
                    match = re.search(rf'"{key}"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw_content)
                    if match:
                        parsed["corrected_fields"][key] = match.group(1).replace('\\"', '"').replace('\\n', ' ')

        # Extract parsed elements
        pass_rules = parsed.get("pass_rules", [])
        corrected_category = parsed.get("corrected_category")
        corrected_fields = parsed.get("corrected_fields", {})

        if not isinstance(pass_rules, list):
            pass_rules = []
        if not isinstance(corrected_fields, dict):
            corrected_fields = {}

        # Map field names to rule IDs
        field_to_rule_map = {
            "product_name": "R6_1_A",
            "manufacturer_name": "R6_1_B",
            "net_quantity": "R6_1_C",
            "manufacture_date": "R6_1_D",
            "mrp": "R6_1_E",
            "consumer_care": "R6_1_H",
            "fssai_license": "FSSAI_1",
            "expiry_date": "BB_1",
            "batch_number": "BATCH_1",
            "ingredients": "ING_1",
            "allergens": "ALLRG_1",
            "storage_instructions": "STOR_1",
            "country_of_origin": "COO_1",
            "veg_nonveg": "VEG_1",
            "mfg_license": "MFG_LIC",
            "composition": "COMP_1",
            "dosage": "DOSE_1",
            "warnings": "WARN_1",
            "schedule_classification": "SCHED_1",
        }

        # Any non-empty corrected field should be registered in pass_rules
        for f_name, f_val in corrected_fields.items():
            if f_val and str(f_val).strip() and str(f_val).strip().lower() not in ("null", "none", "n/a"):
                target_rid = field_to_rule_map.get(f_name)
                if target_rid and target_rid not in pass_rules:
                    pass_rules.append(target_rid)

        for rule in initial_report:
            rid = rule["rule_id"]
            if rid in pass_rules:
                rule["status"] = "pass"
                rule["details"] = "Verified compliant by AI Vision Evaluator."

            # Update evidence if field is present in corrected_fields
            target_field = None
            for fname, r_id in field_to_rule_map.items():
                if r_id == rid:
                    target_field = fname
                    break

            if target_field and target_field in corrected_fields:
                f_val = corrected_fields[target_field]
                if f_val and str(f_val).strip() and str(f_val).strip().lower() not in ("null", "none"):
                    rule["evidence"] = str(f_val).strip()
                    rule["status"] = "pass"
                    rule["details"] = f"Declared: {rule['evidence']} (Verified & corrected by AI Vision Evaluator)"

        return {
            "checks": initial_report,
            "corrected_category": corrected_category,
            "corrected_fields": corrected_fields,
            "pass_rules": pass_rules,
        }

    except Exception as e:
        logger.error(f"AI Evaluation failed: {e}")
        logger.error(f"RAW CONTENT WAS:\n{raw_content if 'raw_content' in locals() else 'None'}")
        return {
            "checks": initial_report,
            "corrected_category": None,
            "corrected_fields": {},
            "pass_rules": [],
        }
