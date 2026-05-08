from __future__ import annotations

from io import BytesIO
from typing import Any
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from .export_branding import resolve_brand_tokens


def _to_num(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def _insight_lines(columns: list[str], rows: list[list[Any]]) -> list[str]:
    if not columns or not rows:
        return ["Dataset is empty or has no columns."]

    lines: list[str] = []
    lines.append(f"Rows analyzed: {len(rows):,}")
    lines.append(f"Columns available: {len(columns):,}")

    numeric_stats: list[tuple[str, float, float, float]] = []
    for idx, name in enumerate(columns[:24]):
        vals = []
        for row in rows[:2500]:
            if idx >= len(row):
                continue
            n = _to_num(row[idx])
            if n is not None:
                vals.append(n)
        if len(vals) >= 4:
            total = float(sum(vals))
            avg = float(total / max(1, len(vals)))
            peak = float(max(vals))
            numeric_stats.append((str(name), total, avg, peak))

    for name, total, avg, peak in numeric_stats[:3]:
        lines.append(f"{name}: total {total:,.2f}, avg {avg:,.2f}, max {peak:,.2f}")

    if not numeric_stats:
        lines.append("No strong numeric signal detected; consider grouping by category for trends.")

    return lines


def table_to_pdf_bytes(
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    *,
    style_guide: str = "",
    insight_lines: list[str] | None = None,
    context_lines: list[str] | None = None,
) -> bytes:
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

    tokens = resolve_brand_tokens(style_guide)
    accent = str(tokens.get("accent") or "#1E5CC6")
    accent_soft = "#E9F0FF"
    if str(tokens.get("brand") or "") == "banking":
        accent_soft = "#EDF2F7"
    elif str(tokens.get("brand") or "") == "operations":
        accent_soft = "#EAF6EE"

    safe_title = str(title or "Export").strip() or "Export"
    summary = f"{len(rows or [])} rows · {len(columns or [])} columns"
    hero = Table(
        [[Paragraph(f"<font color='white'><b>{safe_title}</b></font>", styles["Title"])], [Paragraph(f"<font color='white'>{summary}</font>", styles["Normal"])]],
        colWidths=[760],
    )
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(accent)),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, -1), (-1, -1), 0.2, colors.HexColor("#FFFFFF")),
            ]
        )
    )
    story.append(hero)
    story.append(Spacer(1, 10))

    # Executive context cards before raw table.
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    info_data: list[list[Any]] = []
    info_data.append([Paragraph("<b>Report context</b>", styles["Heading3"])])
    info_data.append([Paragraph(f"Generated: {generated}", styles["BodyText"])])
    info_data.append([Paragraph(f"Style guide: {str(style_guide or 'default')[:240]}", styles["BodyText"])])
    for line in (context_lines or [])[:5]:
        if str(line or "").strip():
            info_data.append([Paragraph(str(line)[:320], styles["BodyText"])])
    info_card = Table(info_data, colWidths=[760])
    info_card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D5DDE8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(info_card)
    story.append(Spacer(1, 8))

    insight_rows = [str(line) for line in (insight_lines or []) if str(line or "").strip()] or _insight_lines(columns or [], rows or [])
    insight_data = [[Paragraph("<b>Executive highlights</b>", styles["Heading3"])]]
    for line in insight_rows[:6]:
        insight_data.append([Paragraph(f"• {line}", styles["BodyText"])])
    insight_card = Table(insight_data, colWidths=[760])
    insight_card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(accent_soft)),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D5DDE8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(insight_card)
    story.append(Spacer(1, 10))

    safe_cols = [str(c) for c in (columns or [])]
    if not safe_cols:
        safe_cols = ["Result"]

    cell_style = styles["BodyText"]
    data = [[Paragraph(f"<b>{c}</b>", cell_style) for c in safe_cols]]
    for r in rows or []:
        vals = list(r or [])
        row_cells = []
        for idx in range(len(safe_cols)):
            val = vals[idx] if idx < len(vals) else ""
            txt = "" if val is None else str(val)
            row_cells.append(Paragraph(txt.replace("\n", "<br/>"), cell_style))
        data.append(row_cells)

    avail_width = 760
    col_count = max(1, len(safe_cols))
    default_w = max(70, min(190, int(avail_width / col_count)))
    col_widths = [default_w for _ in safe_cols]

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(accent)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D5DDE8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(accent_soft)]),
            ]
        )
    )

    story.append(Paragraph("<b>Detailed table</b>", styles["Heading3"]))
    story.append(Spacer(1, 4))
    story.append(tbl)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Generated by BI Lite · {summary}", styles["Italic"]))
    doc.build(story)
    return buf.getvalue()
