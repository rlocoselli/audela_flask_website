from __future__ import annotations

"""Render Report Builder layouts.

Provides a minimal report viewer (HTML handled by template) and PDF export.
The PDF export is intentionally simple: text + tables for question blocks.
It supports basic Image blocks (URL/data URI) and basic per-block styling.
"""

import base64
import re
import urllib.request
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from audela.i18n import tr
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
    lang: str | None = None,
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

    story.append(Paragraph(_escape(title), styles["Title"]))
    story.append(Spacer(1, 10))

    sections = (layout.get("sections") or {})
    sec_label = {
        "header": tr("Cabeçalho", lang),
        "body": tr("Corpo", lang),
        "footer": tr("Rodapé", lang),
    }

    for section_name in ("header", "body", "footer"):
        blocks = sections.get(section_name) or []
        if not blocks:
            continue

        story.append(Paragraph(_escape(sec_label.get(section_name, section_name.capitalize())), styles["Heading2"]))
        story.append(Spacer(1, 6))

        for b in blocks:
            btype = (b.get("type") or "").lower()
            bstyle = b.get("style") if isinstance(b.get("style"), dict) else {}
            # Back-compat: builder used `text` in older versions
            content = (b.get("content") if b.get("content") is not None else b.get("text")) or ""

            if btype in ("text", "markdown"):
                ttl = (b.get("title") or "").strip()
                if ttl:
                    story.append(Paragraph(_escape(ttl), styles["Heading3"]))
                    story.append(Spacer(1, 3))

                if content:
                    pstyle = _styled_paragraph_style(styles["BodyText"], bstyle)
                    story.append(Paragraph(_escape(_markdown_to_text(content)).replace("\n", "<br/>"), pstyle))
                    story.append(Spacer(1, 8))
                continue

            if btype == "image":
                # Title
                ttl = (b.get("title") or "").strip()
                if ttl:
                    story.append(Paragraph(_escape(ttl), styles["Heading3"]))
                    story.append(Spacer(1, 3))

                url = (b.get("url") or b.get("image_url") or "").strip()
                caption = (b.get("caption") or "").strip()
                width_spec = (b.get("width") or "").strip()

                img_flowable = _image_flowable(url, doc.width, width_spec=width_spec)
                if img_flowable is not None:
                    story.append(img_flowable)
                    story.append(Spacer(1, 6))
                else:
                    story.append(Paragraph(_escape(tr("Imagem não disponível", lang)), styles["BodyText"]))
                    story.append(Spacer(1, 6))

                if caption:
                    cap_style = _styled_paragraph_style(styles["BodyText"], bstyle)
                    story.append(Paragraph(_escape(caption), cap_style))
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
                    story.append(Paragraph(_escape(tr("Erro ao executar pergunta: {error}", lang).format(error=str(e))), styles["BodyText"]))
                story.append(Spacer(1, 10))
                continue

        story.append(Spacer(1, 6))

    doc.build(story)
    return buf.getvalue()


def _styled_paragraph_style(base: ParagraphStyle, style_dict: dict[str, Any]) -> ParagraphStyle:
    """Clone a reportlab ParagraphStyle and apply text/background colors, if any."""
    p = ParagraphStyle(name=f"{base.name}_rb", parent=base)
    color = (style_dict.get("color") or "").strip()
    bg = (style_dict.get("background") or "").strip()

    if color:
        try:
            p.textColor = colors.HexColor(color)
        except Exception:
            pass
    if bg:
        try:
            p.backColor = colors.HexColor(bg)
        except Exception:
            pass
    return p


def _image_flowable(url: str, max_width: float, *, width_spec: str = "") -> Image | None:
    """Best-effort image embed:
    - supports data:image/...;base64,...
    - supports http/https URLs (download, capped)
    """
    if not url:
        return None

    img_bytes = None
    try:
        if url.startswith("data:image") and "base64," in url:
            b64 = url.split("base64,", 1)[1]
            img_bytes = base64.b64decode(b64)
        elif url.startswith("http://") or url.startswith("https://"):
            img_bytes = _download_image(url, max_bytes=2_000_000)
        else:
            # unsupported scheme in this minimal implementation
            return None
    except Exception:
        return None

    if not img_bytes:
        return None

    bio = BytesIO(img_bytes)
    try:
        reader = ImageReader(bio)
        iw, ih = reader.getSize()
    except Exception:
        return None

    # Decide desired width
    desired_w = max_width
    if width_spec:
        w = width_spec.strip()
        if w.endswith("px"):
            try:
                px = float(w[:-2].strip())
                # Rough px->pt conversion (1px ~ 0.75pt at 96dpi)
                desired_w = min(max_width, px * 0.75)
            except Exception:
                desired_w = max_width
        elif w.endswith("%"):
            try:
                pct = float(w[:-1].strip()) / 100.0
                desired_w = max(40, min(max_width, max_width * pct))
            except Exception:
                desired_w = max_width

    # Keep aspect ratio
    scale = desired_w / float(iw) if iw else 1.0
    desired_h = float(ih) * scale if ih else 120.0

    bio.seek(0)
    im = Image(bio, width=desired_w, height=desired_h)
    return im


def _download_image(url: str, *, max_bytes: int = 2_000_000) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AUDELA-ReportBuilder/1.0",
            "Accept": "image/*,*/*;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        ct = (resp.headers.get("Content-Type") or "").lower()
        if "image" not in ct:
            # still allow unknown, but keep small
            pass
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("image too large")
        return data


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
