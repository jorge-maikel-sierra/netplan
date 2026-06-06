"""PDF generation service for project reports.

Uses reportlab Platypus to build multi-table PDFs with optional
embedded map images. All output goes to BytesIO — no disk writes.
"""
from __future__ import annotations

import base64
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 20 * mm

HEADER_BG = colors.HexColor("#2F5496")
HEADER_FG = colors.white
ALT_ROW_BG = colors.HexColor("#D6E4F0")
BORDER_COLOR = colors.HexColor("#8DB4E2")

# Map image max dimensions
MAP_MAX_WIDTH = PAGE_WIDTH - 2 * MARGIN
MAP_MAX_HEIGHT = PAGE_HEIGHT * 0.8


# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle(
    "ReportTitle",
    parent=_STYLES["Title"],
    fontSize=18,
    spaceAfter=6,
)
_SUBTITLE_STYLE = ParagraphStyle(
    "ReportSubtitle",
    parent=_STYLES["Normal"],
    fontSize=11,
    textColor=colors.grey,
    spaceAfter=12,
)
_SECTION_STYLE = ParagraphStyle(
    "SectionHeader",
    parent=_STYLES["Heading2"],
    fontSize=13,
    textColor=HEADER_BG,
    spaceBefore=12,
    spaceAfter=6,
)
_CELL_STYLE = ParagraphStyle(
    "CellStyle",
    fontName="Helvetica",
    fontSize=8,
    leading=10,
)


def _make_table(
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float] | None = None,
) -> Table:
    """Build a styled Table with header row and alternating row colors."""
    styled_headers = [Paragraph(h, _CELL_STYLE) for h in headers]
    data = [styled_headers]
    for row in rows:
        data.append([Paragraph(str(c), _CELL_STYLE) for c in row])

    t = Table(data, colWidths=col_widths, repeatRows=1)

    style_cmds: list = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    # Alternate row colors (skip header row)
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ALT_ROW_BG))

    t.setStyle(TableStyle(style_cmds))
    return t


def _safe_decode_image(base64_str: Optional[str]) -> Optional[BytesIO]:
    """Decode a base64-encoded PNG image. Returns None on empty/invalid."""
    if not base64_str:
        return None
    try:
        raw = base64.b64decode(base64_str)
    except (base64.binascii.Error, ValueError, TypeError):
        return None
    if len(raw) < 50:  # Too small to be a real image
        return None
    buf = BytesIO(raw)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_pdf_report(
    project: dict,
    nodes: list[dict],
    edges: list[dict],
    mst_result: Optional[dict],
    map_image_base64: Optional[str] = None,
) -> BytesIO:
    """Generate a PDF report for a project.

    The report contains:
      - Title and project summary
      - Nodes table: Label, Type, Latitude, Longitude
      - Edges table: Node A → Node B, Cost, Constraint, In MST
      - Optional embedded map image

    Args:
        project: Project dict with name, description, etc.
        nodes: List of node dicts with name, type, lat, lng.
        edges: List of edge dicts with node_a_id, node_b_id, cost, constraint_type.
        mst_result: Optional dict with total_cost, edge_ids, algorithm.
        map_image_base64: Optional base64-encoded PNG image data.

    Returns:
        BytesIO containing the PDF data.
    """
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    story: list = []

    # -------------------------------------------------------------------
    # Title & Summary
    # -------------------------------------------------------------------
    title = project.get("name", "Untitled Project")
    story.append(Paragraph(title, _TITLE_STYLE))

    desc = project.get("description")
    if desc:
        story.append(Paragraph(str(desc), _SUBTITLE_STYLE))

    # Summary stats
    summary_lines = [
        f"<b>Nodes:</b> {len(nodes)}",
        f"<b>Edges:</b> {len(edges)}",
    ]
    if mst_result:
        total_cost = mst_result.get("total_cost", 0)
        algorithm = mst_result.get("algorithm", "kruskal")
        summary_lines.append(f"<b>MST Total Cost:</b> {total_cost}")
        summary_lines.append(f"<b>Algorithm:</b> {algorithm}")

    summary_text = " &nbsp;·&nbsp; ".join(summary_lines)
    story.append(Paragraph(summary_text, _SUBTITLE_STYLE))
    story.append(Spacer(1, 6 * mm))

    # -------------------------------------------------------------------
    # Nodes Table
    # -------------------------------------------------------------------
    story.append(Paragraph("Nodes", _SECTION_STYLE))

    node_headers = ["Label", "Type", "Latitude", "Longitude"]
    node_col_widths = [80, 60, 70, 70]
    node_rows: list[list[str]] = []
    sorted_nodes = sorted(nodes, key=lambda n: str(n.get("name", "")))
    for n in sorted_nodes:
        node_rows.append([
            str(n.get("name", "")),
            str(n.get("type", "")),
            str(n.get("lat", "")),
            str(n.get("lng", "")),
        ])

    story.append(_make_table(node_headers, node_rows, node_col_widths))
    story.append(Spacer(1, 6 * mm))

    # -------------------------------------------------------------------
    # Edges Table
    # -------------------------------------------------------------------
    story.append(Paragraph("Edges", _SECTION_STYLE))

    edge_headers = ["Node A", "Node B", "Cost", "Constraint", "In MST"]
    edge_col_widths = [70, 70, 50, 70, 45]
    edge_rows: list[list[str]] = []

    # Build node name lookup
    node_name_by_id: dict[str, str] = {
        str(n.get("id", "")): str(n.get("name", "")) for n in nodes
    }

    # Build MST edge ID set
    mst_edge_ids: set[str] = set()
    if mst_result:
        raw_ids = mst_result.get("edge_ids")
        if isinstance(raw_ids, list):
            mst_edge_ids = {str(eid) for eid in raw_ids}

    sorted_edges = sorted(
        edges, key=lambda e: float(e.get("cost", 0)), reverse=True
    )
    for e in sorted_edges:
        a_id = str(e.get("node_a_id", ""))
        b_id = str(e.get("node_b_id", ""))
        edge_id = str(e.get("id", ""))
        in_mst = "Yes" if edge_id in mst_edge_ids else "No"
        edge_rows.append([
            node_name_by_id.get(a_id, a_id[:8]),
            node_name_by_id.get(b_id, b_id[:8]),
            str(e.get("cost", "")),
            str(e.get("constraint_type", "normal")),
            in_mst,
        ])

    story.append(_make_table(edge_headers, edge_rows, edge_col_widths))
    story.append(Spacer(1, 6 * mm))

    # -------------------------------------------------------------------
    # Map Image (optional)
    # -------------------------------------------------------------------
    if map_image_base64:
        img_buf = _safe_decode_image(map_image_base64)
        if img_buf is not None:
            img = Image(img_buf)
            # Scale to fit page width, maintaining aspect ratio
            aspect = img.drawHeight / img.drawWidth if img.drawWidth else 1
            img.drawWidth = min(MAP_MAX_WIDTH, img.drawWidth)
            img.drawHeight = min(img.drawWidth * aspect, MAP_MAX_HEIGHT)
            story.append(Paragraph("Network Map", _SECTION_STYLE))
            story.append(img)

    # -------------------------------------------------------------------
    # Build PDF
    # -------------------------------------------------------------------
    doc.build(story)
    buf.seek(0)
    return buf
