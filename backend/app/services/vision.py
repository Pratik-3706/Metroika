"""
Vision service — sends product images to the Kimi K2.5 vision model
via the OpenAI-compatible API for label text extraction and analysis.
"""

import base64
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import openai

from app.config import settings

logger = logging.getLogger(__name__)

# System prompt that instructs the vision model what to extract
EXTRACTION_SYSTEM_PROMPT = """You are an expert Legal Metrology compliance analyst for India.
You are analyzing images of a packaged commodity label to extract mandatory declarations
required under the Legal Metrology (Packaged Commodities) Rules, 2011.

Analyze ALL the provided images carefully (they show different sides/angles of the SAME product).
Extract the following information from the labels. If a field is not visible in any image, set it to null.

Return ONLY a valid JSON object with these exact keys:

{
  "product_name": "The common/generic name of the commodity",
  "manufacturer_name": "Name of the manufacturer, packer, or importer",
  "manufacturer_address": "Full address of the manufacturer/packer/importer",
  "net_quantity": "The net quantity with unit (e.g., '500 g', '1 L', '100 ml')",
  "mrp": "The MRP as printed (e.g., 'MRP ₹150.00 (inclusive of all taxes)')",
  "manufacture_date": "Month and year of manufacture/packing/import as printed",
  "expiry_date": "Expiry/best before date if visible",
  "consumer_care": "Consumer care details - name, phone, email, address",
  "country_of_origin": "Country of origin if mentioned (especially for imported goods)",
  "is_imported": true/false,
  "batch_number": "Batch/lot number if visible",
  "fssai_license": "FSSAI license number if visible (for food products)",
  "barcode_visible": true/false,
  "ingredients_list": true/false,
  "nutritional_info": true/false,
  "unit_sale_price": "Unit sale price if mentioned",
  "language_english": true/false,
  "language_hindi": true/false,
  "language_other": "Other languages if any",
  "declarations_on_front": true/false,
  "font_appears_readable": true/false,
  "font_size_assessment": "Assessment of font size - 'adequate', 'small', 'very_small', 'not_determinable'",
  "pdp_area_estimate": "Estimated PDP area category: 'under_50_cm2', '50_to_100_cm2', '100_to_500_cm2', 'over_500_cm2'",
  "mrp_format_correct": true/false,
  "mrp_includes_tax_declaration": true/false,
  "additional_observations": "Any other relevant observations about compliance",
  "overall_assessment": "Brief overall compliance assessment",
  "confidence_score": 0.0 to 1.0
}

IMPORTANT RULES:
- Analyze ALL images together as they show different sides of the SAME product.
- Be thorough and precise in extracting text from the labels.
- If you can partially read a field, include what you can read with a note.
- For MRP, check if it includes "inclusive of all taxes" or similar wording.
- For date, check the format (MM/YYYY or Month YYYY as prescribed).
- Return ONLY the JSON object, no other text or markdown formatting.
"""


def _encode_image(image_path: str) -> str:
    """Read an image file and return its base64-encoded string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


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


async def analyze_product_images(image_paths: List[str]) -> Dict:
    """
    Send multiple product images to the Kimi K2.5 vision model
    and extract label information as structured JSON.

    Args:
        image_paths: List of absolute paths to product images.

    Returns:
        Parsed JSON dict of extracted label data, or error dict.
    """
    client = openai.OpenAI(
        base_url=settings.aicredits_base_url,
        api_key=settings.aicredits_api_key,
    )

    # Build the content array with text prompt + all images
    content: list = [
        {
            "type": "text",
            "text": (
                f"I'm providing {len(image_paths)} image(s) of a packaged commodity. "
                "These are different views (front, back, sides) of the SAME product. "
                "Please analyze all images and extract the mandatory declarations."
            ),
        }
    ]

    for img_path in image_paths:
        try:
            b64 = _encode_image(img_path)
            mime = _get_mime_type(img_path)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{b64}",
                    },
                }
            )
        except Exception as e:
            logger.warning(f"Could not encode image {img_path}: {e}")

    if len(content) < 2:
        return {"error": "No images could be loaded for analysis."}

    try:
        response = client.chat.completions.create(
            model=settings.vision_model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=4096,
            temperature=0.1,
        )

        raw_content = response.choices[0].message.content
        if not raw_content:
            return {"error": "AI returned an empty response. The model may have refused the request or encountered an internal error."}

        raw_text = raw_content.strip()

        # Try to extract the JSON block if the model wrapped it in markdown
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].strip()
            if raw_text.startswith("json"):
                raw_text = raw_text[4:].strip()

        # As a final fallback, extract everything between the first { and last }
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            raw_text = raw_text[start_idx:end_idx+1]

        parsed = json.loads(raw_text)
        parsed["_raw_response"] = response.choices[0].message.content
        return parsed

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        return {
            "error": "AI response was not valid JSON",
            "_raw_response": raw_text if "raw_text" in dir() else "No response",
        }
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return {"error": f"API error: {str(e)}"}
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        return {"error": f"Analysis failed: {str(e)}"}
