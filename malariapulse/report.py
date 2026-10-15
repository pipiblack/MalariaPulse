"""PDF export for structured MalariaPulse AI operations reviews."""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#15233A")
MUTED = colors.HexColor("#647188")
BLUE = colors.HexColor("#246BFD")
BLUE_DEEP = colors.HexColor("#1555D7")
BLUE_SOFT = colors.HexColor("#E9F0FF")
GREEN = colors.HexColor("#14865F")
AMBER = colors.HexColor("#E49B24")
RED = colors.HexColor("#E6534C")
BORDER = colors.HexColor("#DDE4EE")
PALE = colors.HexColor("#F5F7FA")


def _clean_text(value: Any) -> str:
    return escape(str(value or "")).replace("\n", "<br/>")


def _format_timestamp(value: str | None) -> str:
    if not value:
        return "Not supplied"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%d %B %Y, %H:%M UTC")
    except ValueError:
        return value


def report_jurisdiction(result: dict[str, Any], dataset: dict[str, Any]) -> str:
    scope = result.get("scope") or {}
    subcounty = str(scope.get("subcounty") or "").strip()
    if subcounty:
        lowered = subcounty.lower().replace(" ", "").replace("-", "")
        return subcounty if lowered.endswith("subcounty") else f"{subcounty} Sub-County"
    source = result.get("source") or dataset.get("metadata") or {}
    county = str(source.get("county") or "County network").strip()
    return county if county.lower().endswith("county") else f"{county} County"


def ai_report_filename(result: dict[str, Any], dataset: dict[str, Any]) -> str:
    jurisdiction = report_jurisdiction(result, dataset)
    slug = re.sub(r"[^a-z0-9]+", "-", jurisdiction.lower()).strip("-")
    source = result.get("source") or dataset.get("metadata") or {}
    week = re.sub(r"[^A-Za-z0-9-]+", "-", str(source.get("reportingWeek") or "current"))
    return f"malariapulse-ai-report-{slug}-{week}.pdf"


def _report_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "MPTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "section": ParagraphStyle(
            "MPSection",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=BLUE_DEEP,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "MPBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=13.2,
            textColor=INK,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "MPSmall",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        ),
        "label": ParagraphStyle(
            "MPLabel",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            textColor=MUTED,
        ),
        "finding": ParagraphStyle(
            "MPFinding",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=INK,
            spaceAfter=3,
        ),
        "table": ParagraphStyle(
            "MPTable",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.2,
            textColor=INK,
        ),
        "table_header": ParagraphStyle(
            "MPTableHeader",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8.5,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "risk": ParagraphStyle(
            "MPRisk",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
    }


def build_ai_report_pdf(result: dict[str, Any], dataset: dict[str, Any]) -> bytes:
    """Render a structured AI review as a multipage PDF with a first-page letterhead."""

    review = result["review"]
    metadata = result.get("source") or dataset.get("metadata") or {}
    scope = result.get("scope") or {}
    jurisdiction = report_jurisdiction(result, dataset)
    scope_label = str(scope.get("label") or jurisdiction)
    page_width, page_height = A4
    buffer = BytesIO()
    styles = _report_styles()

    document = BaseDocTemplate(
        buffer,
        pagesize=A4,
        title=f"MalariaPulse AI Operations Review - {jurisdiction}",
        author="MalariaPulse",
        subject="Aggregate malaria operations review",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    def draw_footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.4)
        canvas.line(18 * mm, 13 * mm, page_width - 18 * mm, 13 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 9 * mm, "MalariaPulse · Draft for authorized public-health review")
        canvas.drawRightString(page_width - 18 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    def draw_first_page(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFillColor(BLUE_DEEP)
        canvas.rect(0, page_height - 34 * mm, page_width, 34 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(18 * mm, page_height - 12 * mm, "MALARIAPULSE")
        canvas.setFont("Helvetica-Bold", 17)
        letterhead = jurisdiction.upper()
        if stringWidth(letterhead, "Helvetica-Bold", 17) > page_width - 36 * mm:
            canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(18 * mm, page_height - 23 * mm, letterhead)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            page_width - 18 * mm,
            page_height - 12 * mm,
            f"{metadata.get('country', '')} · Reporting week {metadata.get('reportingWeek', 'Not supplied')}",
        )
        canvas.drawRightString(page_width - 18 * mm, page_height - 24 * mm, "AI OPERATIONS REVIEW")
        canvas.restoreState()
        draw_footer(canvas, doc)

    first_frame = Frame(
        18 * mm,
        18 * mm,
        page_width - 36 * mm,
        page_height - 60 * mm,
        id="first-page-frame",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    later_frame = Frame(
        18 * mm,
        18 * mm,
        page_width - 36 * mm,
        page_height - 38 * mm,
        id="later-page-frame",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    document.addPageTemplates(
        [
            PageTemplate(
                id="first-page",
                frames=[first_frame],
                onPage=draw_first_page,
                autoNextPageTemplate="later-pages",
            ),
            PageTemplate(id="later-pages", frames=[later_frame], onPage=draw_footer),
        ]
    )

    risk_level = str(review.get("overallRisk") or "watch").lower()
    risk_colors = {"critical": RED, "high": colors.HexColor("#D97706"), "watch": AMBER, "low": GREEN}
    risk_color = risk_colors.get(risk_level, MUTED)
    story: list[Any] = [
        Paragraph(_clean_text(review.get("headline")), styles["title"]),
        Table(
            [
                [
                    Paragraph("RISK LEVEL", styles["label"]),
                    Paragraph(_clean_text(risk_level.upper()), styles["risk"]),
                    Paragraph("REVIEW SCOPE", styles["label"]),
                    Paragraph(_clean_text(scope_label), styles["body"]),
                ]
            ],
            colWidths=[24 * mm, 29 * mm, 28 * mm, 93 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PALE),
                    ("BACKGROUND", (1, 0), (1, 0), risk_color),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Paragraph("Executive summary", styles["section"]),
        Paragraph(_clean_text(review.get("executiveSummary")), styles["body"]),
        Paragraph("Key findings", styles["section"]),
    ]

    for index, finding in enumerate(review.get("keyFindings") or [], start=1):
        finding_block = [
            Paragraph(f"{index}. {_clean_text(finding.get('title'))}", styles["finding"]),
            Paragraph(f"<b>Evidence:</b> {_clean_text(finding.get('evidence'))}", styles["body"]),
            Paragraph(f"<b>Operational implication:</b> {_clean_text(finding.get('implication'))}", styles["body"]),
            Spacer(1, 2 * mm),
        ]
        story.append(KeepTogether(finding_block))

    story.append(Paragraph("Ranked priorities", styles["section"]))
    priorities = review.get("priorities") or []
    if priorities:
        priority_rows = [
            [
                Paragraph("Rank", styles["table_header"]),
                Paragraph("Action and rationale", styles["table_header"]),
                Paragraph("Owner", styles["table_header"]),
                Paragraph("Timeframe", styles["table_header"]),
                Paragraph("Approval", styles["table_header"]),
            ]
        ]
        for priority in sorted(priorities, key=lambda item: item.get("rank", 999)):
            priority_rows.append(
                [
                    Paragraph(_clean_text(priority.get("rank")), styles["table"]),
                    Paragraph(
                        f"<b>{_clean_text(priority.get('action'))}</b><br/>{_clean_text(priority.get('rationale'))}",
                        styles["table"],
                    ),
                    Paragraph(_clean_text(priority.get("owner")), styles["table"]),
                    Paragraph(_clean_text(priority.get("timeframe")), styles["table"]),
                    Paragraph("Required" if priority.get("requiresApproval") else "Not required", styles["table"]),
                ]
            )
        story.append(
            Table(
                priority_rows,
                colWidths=[12 * mm, 66 * mm, 31 * mm, 31 * mm, 34 * mm],
                repeatRows=1,
                splitByRow=1,
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), BLUE_DEEP),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                ),
            )
        )
    else:
        story.append(Paragraph("No ranked priorities were returned for this review.", styles["body"]))

    data_quality = review.get("dataQuality") or {}
    quality_content = [
        Paragraph("Data quality", styles["section"]),
        Paragraph(f"<b>Freshness:</b> {_clean_text(data_quality.get('freshness'))}", styles["body"]),
        Paragraph(f"<b>Completeness:</b> {_clean_text(data_quality.get('completeness'))}", styles["body"]),
    ]
    concerns = data_quality.get("concerns") or []
    quality_content.extend(Paragraph(f"• {_clean_text(item)}", styles["body"]) for item in concerns)
    story.extend(quality_content)

    story.append(Paragraph("Limitations", styles["section"]))
    limitations = review.get("limitations") or []
    if limitations:
        story.extend(Paragraph(f"• {_clean_text(item)}", styles["body"]) for item in limitations)
    else:
        story.append(Paragraph("No additional limitations were returned.", styles["body"]))

    story.extend(
        [
            Spacer(1, 4 * mm),
            Table(
                [
                    [Paragraph("Generated", styles["label"]), Paragraph(_clean_text(_format_timestamp(result.get("generatedAt"))), styles["small"])],
                    [Paragraph("Source updated", styles["label"]), Paragraph(_clean_text(_format_timestamp(result.get("sourceUpdatedAt"))), styles["small"])],
                    [Paragraph("Model", styles["label"]), Paragraph(_clean_text(result.get("model")), styles["small"])],
                ],
                colWidths=[32 * mm, 142 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), BLUE_SOFT),
                        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                ),
            ),
            Spacer(1, 3 * mm),
            Paragraph(
                "This AI-assisted review uses aggregate operational data. It is not an outbreak declaration, diagnosis, or authorization to dispatch supplies or public messages.",
                styles["small"],
            ),
        ]
    )

    document.build(story)
    return buffer.getvalue()
