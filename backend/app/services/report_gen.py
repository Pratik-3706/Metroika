"""
PDF report generation service using ReportLab.
Generates color-coded compliance reports with product images and rule references.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    PageBreak,
    HRFlowable,
)

from app.config import settings

logger = logging.getLogger(__name__)

# Color scheme
COLOR_PASS = colors.HexColor("#10B981")
COLOR_FAIL = colors.HexColor("#EF4444")
COLOR_WARNING = colors.HexColor("#F59E0B")
COLOR_NA = colors.HexColor("#6B7280")
COLOR_HEADER_BG = colors.HexColor("#1E293B")
COLOR_HEADER_TEXT = colors.HexColor("#F8FAFC")
COLOR_ACCENT = colors.HexColor("#6366F1")

STATUS_COLORS = {
    "pass": COLOR_PASS,
    "fail": COLOR_FAIL,
    "warning": COLOR_WARNING,
    "not_applicable": COLOR_NA,
}

STATUS_LABELS = {
    "pass": "✓ PASS",
    "fail": "✗ FAIL",
    "warning": "⚠ WARNING",
    "not_applicable": "— N/A",
}


def generate_report(
    product_name: str,
    product_id: int,
    barcode_data: Optional[str],
    image_paths: List[str],
    checks: List[Dict],
    score_info: Dict,
    extracted_data: Dict,
    annotated_image_paths: Optional[List[str]] = None,
) -> str:
    """
    Generate a PDF compliance report.

    Returns:
        Absolute path to the generated PDF file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"compliance_report_{product_id}_{timestamp}.pdf"
    filepath = str(settings.report_dir / filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=20,
        textColor=COLOR_HEADER_BG,
        spaceAfter=6,
        alignment=1,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.grey,
        alignment=1,
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=COLOR_ACCENT,
        spaceBefore=16,
        spaceAfter=8,
        borderPadding=(0, 0, 4, 0),
    )
    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
    )
    detail_style = ParagraphStyle(
        "DetailText",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#4B5563"),
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#1F2937"),
    )
    ext_val_style = ParagraphStyle(
        "ExtVal",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1F2937"),
    )

    elements = []

    # ----- Title -----
    elements.append(Paragraph("METROIKA", title_style))
    elements.append(
        Paragraph("Legal Metrology Compliance Report", subtitle_style)
    )
    elements.append(
        Paragraph(
            f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}",
            subtitle_style,
        )
    )
    elements.append(HRFlowable(width="100%", thickness=1, color=COLOR_ACCENT))
    elements.append(Spacer(1, 12))

    # ----- Product Info -----
    elements.append(Paragraph("Product Information", section_style))
    prod_data = [
        ["Product Name", product_name or "Not specified"],
        ["Product ID", str(product_id)],
        ["Barcode", barcode_data or "Not detected"],
        ["Images Analyzed", str(len(image_paths))],
    ]
    prod_table = Table(prod_data, colWidths=[5 * cm, 12 * cm])
    prod_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(prod_table)
    elements.append(Spacer(1, 12))

    # ----- Compliance Score Summary -----
    elements.append(Paragraph("Compliance Summary", section_style))
    score = score_info.get("score", 0)
    status = score_info.get("status", "pending")

    if status == "compliant":
        score_color = COLOR_PASS
        score_label = "COMPLIANT"
    elif status == "warning":
        score_color = COLOR_WARNING
        score_label = "WARNINGS"
    else:
        score_color = COLOR_FAIL
        score_label = "NON-COMPLIANT"

    summary_data = [
        [
            Paragraph(
                f'<font size="24" color="{score_color.hexval()}">{score:.0f}%</font>',
                styles["Normal"],
            ),
            Paragraph(
                f'<font size="14" color="{score_color.hexval()}">{score_label}</font>',
                styles["Normal"],
            ),
        ],
    ]
    stats_data = [
        ["Total Checks", str(score_info.get("total", 0))],
        ["Passed", str(score_info.get("passed", 0))],
        ["Failed", str(score_info.get("failed", 0))],
        ["Warnings", str(score_info.get("warnings", 0))],
    ]
    stats_table = Table(stats_data, colWidths=[5 * cm, 3 * cm])
    stats_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TEXTCOLOR", (1, 1), (1, 1), COLOR_PASS),
                ("TEXTCOLOR", (1, 2), (1, 2), COLOR_FAIL),
                ("TEXTCOLOR", (1, 3), (1, 3), COLOR_WARNING),
            ]
        )
    )
    elements.append(stats_table)
    elements.append(Spacer(1, 16))

    # ----- Detailed Checks -----
    elements.append(Paragraph("Detailed Compliance Checks", section_style))
    elements.append(
        Paragraph(
            "Based on the Legal Metrology (Packaged Commodities) Rules, 2011",
            detail_style,
        )
    )
    elements.append(Spacer(1, 8))

    # Table header
    check_header = ["#", "Rule", "Reference", "Status", "Details"]
    check_rows = [check_header]

    for i, c in enumerate(checks, 1):
        status_label = STATUS_LABELS.get(c["status"], c["status"])
        check_rows.append(
            [
                str(i),
                Paragraph(c["rule_name"], table_cell_style),
                Paragraph(c["rule_reference"], table_cell_style),
                status_label,
                Paragraph(c["details"], table_cell_style),
            ]
        )

    check_table = Table(
        check_rows,
        colWidths=[1 * cm, 4.5 * cm, 2.5 * cm, 2.5 * cm, 7 * cm],
        repeatRows=1,
    )

    # Build table style with color-coded status column
    table_style_cmds = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_HEADER_TEXT),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
    ]

    # Color the status cells
    for i, c in enumerate(checks, 1):
        color = STATUS_COLORS.get(c["status"], COLOR_NA)
        table_style_cmds.append(("TEXTCOLOR", (3, i), (3, i), color))
        table_style_cmds.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))

    check_table.setStyle(TableStyle(table_style_cmds))
    elements.append(check_table)
    elements.append(Spacer(1, 16))

    # ----- Extracted Data Summary -----
    elements.append(Paragraph("Extracted Label Data", section_style))
    key_fields = [
        ("Product Name", extracted_data.get("product_name")),
        ("Manufacturer", extracted_data.get("manufacturer_name")),
        ("Address", extracted_data.get("manufacturer_address")),
        ("Net Quantity", extracted_data.get("net_quantity")),
        ("MRP", extracted_data.get("mrp")),
        ("Manufacture Date", extracted_data.get("manufacture_date")),
        ("Expiry Date", extracted_data.get("expiry_date")),
        ("Consumer Care", extracted_data.get("consumer_care")),
        ("Country of Origin", extracted_data.get("country_of_origin")),
        ("FSSAI License", extracted_data.get("fssai_license")),
        ("Batch Number", extracted_data.get("batch_number")),
        ("Ingredients", extracted_data.get("ingredients")),
        ("Allergens", extracted_data.get("allergens")),
        ("Nutritional Info", extracted_data.get("nutritional_info")),
        ("Storage Instructions", extracted_data.get("storage_instructions")),
        ("Veg / Non-Veg", extracted_data.get("veg_nonveg")),
    ]
    ext_rows = []
    for label, value in key_fields:
        val_str = str(value) if value else "—"
        ext_rows.append([label, Paragraph(val_str, ext_val_style)])

    ext_table = Table(ext_rows, colWidths=[4 * cm, 13.5 * cm])
    ext_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ]
        )
    )
    elements.append(ext_table)

    # ----- Annotated OCR Images -----
    if annotated_image_paths:
        elements.append(PageBreak())
        elements.append(Paragraph("OCR Analysis — Annotated Images", section_style))
        elements.append(
            Paragraph(
                '<font size="8" color="grey">'
                "Color-coded bounding boxes show detected text regions. "
                "Blue=Net Qty, Red=MRP, Orange=Dates, Green=Manufacturer, "
                "Purple=FSSAI, Cyan=Nutritional, Pink=Ingredients."
                "</font>",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 8))

        for ann_path in annotated_image_paths[:6]:
            try:
                if Path(ann_path).exists():
                    img = RLImage(ann_path, width=16 * cm, height=11 * cm)
                    img.hAlign = "CENTER"
                    elements.append(img)
                    elements.append(
                        Paragraph(
                            f'<font size="7" color="grey">{Path(ann_path).name}</font>',
                            styles["Normal"],
                        )
                    )
                    elements.append(Spacer(1, 8))
            except Exception as e:
                logger.warning(f"Could not add annotated image to report: {e}")

    # ----- Product Images -----
    elements.append(PageBreak())
    elements.append(Paragraph("Original Product Images", section_style))

    for img_path in image_paths[:6]:  # Max 6 images
        try:
            if Path(img_path).exists():
                img = RLImage(img_path, width=14 * cm, height=10 * cm)
                img.hAlign = "CENTER"
                elements.append(img)
                elements.append(
                    Paragraph(
                        f'<font size="7" color="grey">{Path(img_path).name}</font>',
                        styles["Normal"],
                    )
                )
                elements.append(Spacer(1, 8))
        except Exception as e:
            logger.warning(f"Could not add image to report: {e}")

    # ----- Footer -----
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elements.append(
        Paragraph(
            '<font size="7" color="grey">'
            "This report was generated by Metroika — Legal Metrology Compliance Checker. "
            "Based on Legal Metrology (Packaged Commodities) Rules, 2011 with amendments up to 2026. "
            "This is an AI-assisted automated assessment and should be verified by a qualified inspector."
            "</font>",
            styles["Normal"],
        )
    )

    # Build the PDF
    doc.build(elements)
    logger.info(f"Report generated: {filepath}")
    return filepath
