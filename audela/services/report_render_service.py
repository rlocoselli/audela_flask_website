from __future__ import annotations

"""Render Report Builder layouts.

Provides a minimal report viewer (HTML handled by template) and PDF export.
The PDF export is intentionally simple: text + tables for question blocks.
"""

import re
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .query_service import execute_sql


def report_to_pdf_bytes(
    *,
    title: str,
    report: Any,
    source: Any,
    tenant_id: int,
    questions_by_id: dict[int, Any],
    row_limit: int = 30,
    col_limit: int = 8,
) -> bytes:
    layout = report.layout_json or {}

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
        title=title,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []

    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 10))

    sections = (layout.get("sections") or {})
    for section_name in ("header", "body", "footer"):
        blocks = sections.get(section_name) or []
        if not blocks:
            continue

        story.append(Paragraph(section_name.capitalize(), styles["Heading2"]))
        story.append(Spacer(1, 6))

        for b in blocks:
            btype = (b.get("type") or "").lower()
            if btype in ("text", "markdown"):
                ttl = (b.get("title") or "").strip()
                content = (b.get("content") or "").strip()
                if ttl:
                    story.append(Paragraph(_escape(ttl), styles["Heading3"]))
                    story.append(Spacer(1, 3))
                if content:
                    story.append(Paragraph(_escape(_markdown_to_text(content)).replace("\n", "<br/>"), styles["BodyText"]))
                    story.append(Spacer(1, 8))
                continue

            if btype == "question":
                qid = int(b.get("question_id") or 0)
                q = questions_by_id.get(qid)
                if not q:
                    continue
                story.append(Paragraph(_escape(q.name), styles["Heading3"]))
                story.append(Spacer(1, 3))
                try:
                    res = execute_sql(source, q.sql_text or "", {"tenant_id": tenant_id}, row_limit=row_limit)
                    cols = res.get("columns") or []
                    rows = res.get("rows") or []
                    cols = cols[:col_limit]
                    rows = [r[:col_limit] for r in rows]
                    data = [cols] + rows
                    tbl = Table(data, repeatRows=1)
                    tbl.setStyle(
                        TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, -1), 8),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ]
                        )
                    )
                    story.append(tbl)
                except Exception as e:
                    story.append(Paragraph(_escape(f"Erro ao executar pergunta: {e}"), styles["BodyText"]))
                story.append(Spacer(1, 10))

        story.append(Spacer(1, 6))

    doc.build(story)
    return buf.getvalue()


def _markdown_to_text(md: str) -> str:
    s = md or ""
    # very light cleanup: remove code fences/inline, list markers
    s = re.sub(r"```[\s\S]*?```", "", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"^\s*[-*+]\s+", "", s, flags=re.M)
    s = re.sub(r"^\s*#{1,6}\s+", "", s, flags=re.M)
    return s.strip()


def _escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
