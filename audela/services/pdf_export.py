from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def table_to_pdf_bytes(title: str, columns: list[str], rows: list[list[Any]]) -> bytes:
    """Render a simple table to PDF.

    - This is meant for exporting query results (tables/pivots) rather than pixel-perfect dashboards.
    - Keeps memory usage small and avoids heavy HTML-to-PDF dependencies.
    """

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18,
        title=title or "Export",
    )

    styles = getSampleStyleSheet()
    story = []
    if title:
        story.append(Paragraph(title, styles["Title"]))
        story.append(Spacer(1, 12))

    safe_cols = [str(c) for c in (columns or [])]
    data = [safe_cols]
    for r in rows or []:
        data.append(["" if v is None else str(v) for v in (r or [])])

    tbl = Table(data, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfbfb")]),
            ]
        )
    )

    story.append(tbl)
    doc.build(story)
    return buf.getvalue()
