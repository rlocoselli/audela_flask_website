from __future__ import annotations

"""Render Report Builder layouts (HTML viewer handled by template) and PDF export.

This module implements a Crystal/DevExpress-like *band* model:
- report_header (first page only)
- page_header (every page)
- detail (main flow)
- page_footer (every page)
- report_footer (last page only)

Backward compatible with older layouts that used sections: header/body/footer.
"""

import base64
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from audela.i18n import tr
from .query_service import execute_sql


# -----------------------------
# Public API
# -----------------------------


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
    bands = _get_bands(layout)
    settings = layout.get("settings") if isinstance(layout.get("settings"), dict) else {}

    styles = getSampleStyleSheet()

    # Prepare repeating page header/footer flowables (drawn on every page)
    page_header_flows = _blocks_to_flowables(
        bands.get("page_header") or [],
        styles,
        doc_width=A4[0] - 48,
        source=source,
        tenant_id=tenant_id,
        questions_by_id=questions_by_id,
        row_limit=min(10, row_limit),
        col_limit=col_limit,
        lang=lang,
        band_name="page_header",
        for_page_band=True,
    )
    page_footer_flows = _blocks_to_flowables(
        bands.get("page_footer") or [],
        styles,
        doc_width=A4[0] - 48,
        source=source,
        tenant_id=tenant_id,
        questions_by_id=questions_by_id,
        row_limit=min(10, row_limit),
        col_limit=col_limit,
        lang=lang,
        band_name="page_footer",
        for_page_band=True,
    )

    base_margin = 24
    page_number_reserved = 14 if settings.get("page_number", True) else 0

    header_h = _flows_height(page_header_flows, A4[0] - 48)
    footer_h = _flows_height(page_footer_flows, A4[0] - 48)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=base_margin,
        rightMargin=base_margin,
        topMargin=base_margin + header_h,
        bottomMargin=base_margin + footer_h + page_number_reserved,
        title=title,
    )

    # Story: report header (once), detail, report footer (once)
    story: list[Any] = []

    # Title is part of report header by default (Crystal-like)
    story.append(Paragraph(_escape(title), styles["Title"]))
    story.append(Spacer(1, 10))

    story.extend(
        _blocks_to_flowables(
            bands.get("report_header") or [],
            styles,
            doc_width=doc.width,
            source=source,
            tenant_id=tenant_id,
            questions_by_id=questions_by_id,
            row_limit=row_limit,
            col_limit=col_limit,
            lang=lang,
            band_name="report_header",
        )
    )

    story.extend(
        _blocks_to_flowables(
            bands.get("detail") or [],
            styles,
            doc_width=doc.width,
            source=source,
            tenant_id=tenant_id,
            questions_by_id=questions_by_id,
            row_limit=row_limit,
            col_limit=col_limit,
            lang=lang,
            band_name="detail",
        )
    )

    story.extend(
        _blocks_to_flowables(
            bands.get("report_footer") or [],
            styles,
            doc_width=doc.width,
            source=source,
            tenant_id=tenant_id,
            questions_by_id=questions_by_id,
            row_limit=row_limit,
            col_limit=col_limit,
            lang=lang,
            band_name="report_footer",
        )
    )

    page_label = str(settings.get("page_number_label") or "Page {page} / {pages}")

    def _on_page(c: Canvas, d: SimpleDocTemplate):
        _draw_page_band(c, d, page_header_flows, where="top", base_margin=base_margin)
        _draw_page_band(
            c,
            d,
            page_footer_flows,
            where="bottom",
            base_margin=base_margin + page_number_reserved,
        )

    doc.build(
        story,
        onFirstPage=_on_page,
        onLaterPages=_on_page,
        canvasmaker=lambda *a, **k: _NumberedCanvas(*a, page_label=page_label, draw_page_numbers=settings.get("page_number", True), **k),
    )
    return buf.getvalue()


# -----------------------------
# Bands & Flowables
# -----------------------------


def _get_bands(layout: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return normalized bands dict. Backward compatible with sections."""
    bands = layout.get("bands") if isinstance(layout.get("bands"), dict) else None
    if bands:
        out: dict[str, list[dict[str, Any]]] = {}
        for k in ("report_header", "page_header", "detail", "page_footer", "report_footer"):
            v = bands.get(k)
            out[k] = v if isinstance(v, list) else []
        return out

    # Backward compatibility
    sections = layout.get("sections") if isinstance(layout.get("sections"), dict) else {}
    return {
        "report_header": [],
        "page_header": sections.get("header") if isinstance(sections.get("header"), list) else [],
        "detail": sections.get("body") if isinstance(sections.get("body"), list) else [],
        "page_footer": sections.get("footer") if isinstance(sections.get("footer"), list) else [],
        "report_footer": [],
    }


def _blocks_to_flowables(
    blocks: list[dict[str, Any]],
    styles,
    *,
    doc_width: float,
    source: Any,
    tenant_id: int,
    questions_by_id: dict[int, Any],
    row_limit: int,
    col_limit: int,
    lang: str | None,
    band_name: str = "",
    for_page_band: bool = False,
) -> list[Any]:
    out: list[Any] = []
    if band_name == "detail":
        blocks = _coalesce_detail_data_rowsets(blocks)

    for b in blocks or []:
        btype = (b.get("type") or "").lower()
        bstyle = b.get("style") if isinstance(b.get("style"), dict) else {}
        config = b.get("config") if isinstance(b.get("config"), dict) else {}

        # Back-compat: builder used `text` in older versions
        content = (b.get("content") if b.get("content") is not None else b.get("text")) or ""

        if btype in ("text", "markdown"):
            ttl = (b.get("title") or "").strip()
            if ttl:
                out.append(Paragraph(_escape(ttl), styles["Heading3"]))
                out.append(Spacer(1, 3))

            if content:
                pstyle = _styled_paragraph_style(styles["BodyText"], bstyle)
                txt = _escape(_markdown_to_text(content)).replace("\n", "<br/>")
                out.append(Paragraph(_apply_text_markup(txt, bstyle), pstyle))
                out.append(Spacer(1, 8))
            continue

        if btype == "field":
            ttl = (b.get("title") or "").strip()
            kind = (config.get("kind") or "date").strip().lower()
            fmt = (config.get("format") or ("dd/MM/yyyy HH:mm" if kind == "datetime" else "dd/MM/yyyy")).strip()
            val = datetime.now() if kind == "datetime" else date.today()
            text = _format_date(val, fmt)

            if ttl:
                out.append(Paragraph(_escape(ttl), styles["Heading3"]))
                out.append(Spacer(1, 3))

            pstyle = _styled_paragraph_style(styles["BodyText"], bstyle)
            out.append(Paragraph(_apply_text_markup(_escape(text), bstyle), pstyle))
            out.append(Spacer(1, 8))
            continue

        if btype == "data_field":
            ttl = (b.get("title") or "").strip()
            if ttl:
                out.append(Paragraph(_escape(ttl), styles["Heading3"]))
                out.append(Spacer(1, 3))

            cfg = b.get("config") if isinstance(b.get("config"), dict) else {}
            bind = (cfg.get("binding") or {}) if isinstance(cfg.get("binding"), dict) else {}

            try:
                value = _resolve_data_binding_value(bind, source, tenant_id, questions_by_id)
            except Exception:
                value = ""

            value = _apply_bound_format(value, cfg.get("format"))
            if value in (None, ""):
                value = str(cfg.get("empty_text") or "")

            pstyle = _styled_paragraph_style(styles["BodyText"], bstyle)
            out.append(Paragraph(_apply_text_markup(_escape(str(value or "")), bstyle), pstyle))
            out.append(Spacer(1, 8))
            continue

        if btype == "data_rowset":
            ttl = (b.get("title") or "").strip()
            if ttl:
                out.append(Paragraph(_escape(ttl), styles["Heading3"]))
                out.append(Spacer(1, 3))

            cfg = b.get("config") if isinstance(b.get("config"), dict) else {}
            bind = (cfg.get("binding") or {}) if isinstance(cfg.get("binding"), dict) else {}
            cols_meta = b.get("columns_meta") if isinstance(b.get("columns_meta"), list) else []
            headers = [str(c.get("title") or c.get("field") or "") for c in cols_meta]
            col_styles = [c.get("style") if isinstance(c.get("style"), dict) else {} for c in cols_meta]

            rows_rendered: list[list[str]] = []
            group_idx = -1
            group_label_tpl = 'Groupe: {group}'
            group_count = False
            for cidx, cm in enumerate(cols_meta):
                if bool(cm.get("group_key")) and group_idx < 0:
                    group_idx = cidx
                    group_label_tpl = str(cm.get("group_label") or 'Groupe: {group}')
                    group_count = True
            try:
                src_kind = (bind.get("source") or "").strip().lower()
                if src_kind == "question":
                    qid = int(bind.get("question_id") or 0)
                    q = questions_by_id.get(qid)
                    if not q:
                        raise ValueError("Pergunta não encontrada")
                    res = execute_sql(source, q.sql_text or "", {"tenant_id": tenant_id}, row_limit=max(20, row_limit))
                    src_cols = res.get("columns") or []
                    src_rows = res.get("rows") or []
                    idx_map = [_find_col_index(src_cols, str(cm.get("field") or "")) for cm in cols_meta]
                    for rr in src_rows:
                        out_row: list[str] = []
                        for k, cm in enumerate(cols_meta):
                            ridx = idx_map[k]
                            v = rr[ridx] if ridx >= 0 and isinstance(rr, (list, tuple)) and ridx < len(rr) else None
                            s = _apply_bound_format(v, str(cm.get("format") or ""))
                            if s in ("", None):
                                s = str(cm.get("empty_text") or "")
                            out_row.append(str(s or ""))
                        rows_rendered.append(out_row)
                elif src_kind == "table":
                    table_name = _safe_ident(str(bind.get("table") or ""))
                    fields = [_safe_ident(str(cm.get("field") or "")) for cm in cols_meta]
                    sql = f"SELECT {', '.join(fields)} FROM {table_name} LIMIT {max(20, row_limit)}"
                    res = execute_sql(source, sql, {"tenant_id": tenant_id}, row_limit=max(20, row_limit))
                    src_rows = res.get("rows") or []
                    for rr in src_rows:
                        out_row = []
                        for cidx, cm in enumerate(cols_meta):
                            v = rr[cidx] if isinstance(rr, (list, tuple)) and cidx < len(rr) else None
                            s = _apply_bound_format(v, str(cm.get("format") or ""))
                            if s in ("", None):
                                s = str(cm.get("empty_text") or "")
                            out_row.append(str(s or ""))
                        rows_rendered.append(out_row)
            except Exception as e:
                out.append(Paragraph(_escape(tr("Erro ao renderizar registros: {error}", lang).format(error=str(e))), styles["BodyText"]))
                out.append(Spacer(1, 8))
                continue

            if rows_rendered:
                if group_idx >= 0:
                    groups: dict[str, list[list[str]]] = {}
                    for rr in rows_rendered:
                        gval = rr[group_idx] if group_idx < len(rr) else ''
                        groups.setdefault(str(gval), []).append(rr)

                    for gname, grows in groups.items():
                        gtitle = group_label_tpl.replace('{group}', str(gname))
                        if group_count:
                            gtitle = f"{gtitle} ({len(grows)})"
                        out.append(Paragraph(_escape(gtitle), styles["Heading4"]))
                        out.append(Spacer(1, 3))
                        data = [headers] + grows
                        tbl = _safe_table(data, repeat_rows=1)
                        tbl.setStyle(_table_style({"theme": "minimal", "zebra": True, "repeat_header": True}))
                        _apply_zebra_to_table(tbl, enabled=True)
                        _apply_column_styles_to_table(tbl, col_styles)
                        out.append(tbl)
                        out.append(Spacer(1, 6))
                else:
                    data = [headers] + rows_rendered
                    tbl = _safe_table(data, repeat_rows=1)
                    tbl.setStyle(_table_style({"theme": "minimal", "zebra": True, "repeat_header": True}))
                    _apply_zebra_to_table(tbl, enabled=True)
                    _apply_column_styles_to_table(tbl, col_styles)
                    out.append(tbl)
            else:
                out.append(Paragraph(_escape(tr("Sem linhas retornadas.", lang)), styles["BodyText"]))
            out.append(Spacer(1, 8))
            continue

        if btype == "image":
            ttl = (b.get("title") or "").strip()
            if ttl:
                out.append(Paragraph(_escape(ttl), styles["Heading3"]))
                out.append(Spacer(1, 3))

            url = (b.get("url") or b.get("image_url") or "").strip()
            caption = (b.get("caption") or "").strip()
            width_spec = (b.get("width") or "").strip()

            img_flowable = _image_flowable(url, doc_width, width_spec=width_spec)
            if img_flowable is not None:
                out.append(img_flowable)
                out.append(Spacer(1, 6))
            else:
                out.append(Paragraph(_escape(tr("Imagem não disponível", lang)), styles["BodyText"]))
                out.append(Spacer(1, 6))

            if caption:
                cap_style = _styled_paragraph_style(styles["BodyText"], bstyle)
                out.append(Paragraph(_apply_text_markup(_escape(caption), bstyle), cap_style))
                out.append(Spacer(1, 8))
            continue

        if btype == "question":
            qid = int(b.get("question_id") or 0)
            q = questions_by_id.get(qid)
            if not q:
                continue

            ttl = (b.get("title") or "").strip() or q.name
            out.append(Paragraph(_escape(ttl), styles["Heading3"]))
            out.append(Spacer(1, 3))

            table_cfg = (config.get("table") if isinstance(config.get("table"), dict) else {})
            decimals = table_cfg.get("decimals")
            try:
                decimals = int(decimals) if decimals is not None and str(decimals).strip() != "" else None
            except Exception:
                decimals = None

            try:
                res = execute_sql(source, q.sql_text or "", {"tenant_id": tenant_id}, row_limit=row_limit)
                cols = (res.get("columns") or [])[:col_limit]
                rows = [r[:col_limit] for r in (res.get("rows") or [])]

                sort_by = str(table_cfg.get("sort_by") or "").strip()
                sort_dir = str(table_cfg.get("sort_dir") or "asc").strip().lower()
                sort_idx = _find_col_index(cols, sort_by)
                rows = _sort_rows(rows, sort_idx, sort_dir == "desc")

                group_by = str(table_cfg.get("group_by") or "").strip()
                group_label = str(table_cfg.get("group_label") or "{group}")
                group_count = bool(table_cfg.get("group_count"))
                group_idx = _find_col_index(cols, group_by)

                repeat = bool(table_cfg.get("repeat_header", True))

                if group_idx >= 0:
                    groups: dict[str, list[list[Any]]] = {}
                    for rr in rows:
                        gv = rr[group_idx] if group_idx < len(rr) else ""
                        gs = _format_cell(gv, decimals=None)
                        groups.setdefault(gs, []).append(rr)

                    for gname, grows in groups.items():
                        gtitle = group_label.replace("{group}", str(gname or ""))
                        if group_count:
                            gtitle = f"{gtitle} ({len(grows)})"
                        out.append(Paragraph(_escape(gtitle), styles["Heading4"]))
                        out.append(Spacer(1, 3))

                        data = [cols] + [[_format_cell(c, decimals=decimals) for c in r] for r in grows]
                        tbl = _safe_table(data, repeat_rows=1 if repeat else 0)
                        tbl.setStyle(_table_style(table_cfg))
                        _apply_zebra_to_table(tbl, enabled=bool(table_cfg.get("zebra", True)))
                        out.append(tbl)
                        out.append(Spacer(1, 6))
                else:
                    data = [cols] + [[_format_cell(c, decimals=decimals) for c in r] for r in rows]
                    tbl = _safe_table(data, repeat_rows=1 if repeat else 0)
                    tbl.setStyle(_table_style(table_cfg))
                    _apply_zebra_to_table(tbl, enabled=bool(table_cfg.get("zebra", True)))
                    out.append(tbl)
            except Exception as e:
                out.append(
                    Paragraph(
                        _escape(tr("Erro ao executar pergunta: {error}", lang).format(error=str(e))),
                        styles["BodyText"],
                    )
                )

            out.append(Spacer(1, 10))
            continue

        # Unknown block type: ignore

    if for_page_band and out and isinstance(out[-1], Spacer):
        # Keep page bands a bit tighter
        pass
    return out


def _table_style(table_cfg: dict[str, Any]) -> TableStyle:
    theme = (table_cfg.get("theme") or "crystal").strip().lower()

    header_bg = (table_cfg.get("header_bg") or "").strip() or (
        "#e9f2ff" if theme == "devexpress" else "#f2f2f2" if theme == "crystal" else "#ffffff"
    )
    grid = (table_cfg.get("grid") or "").strip() or (
        "#b7c7d6" if theme == "devexpress" else "#cccccc" if theme == "crystal" else "#dddddd"
    )

    st = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
    ]

    if theme == "minimal":
        st += [
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor(grid)),
        ]
    else:
        st += [
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(grid)),
        ]

    return TableStyle(st)


def _styled_paragraph_style(base: ParagraphStyle, style_dict: dict[str, Any]) -> ParagraphStyle:
    """Clone a reportlab ParagraphStyle and apply text/background colors and alignment."""
    p = ParagraphStyle(name=f"{base.name}_rb", parent=base)
    color = (style_dict.get("color") or "").strip()
    bg = (style_dict.get("background") or "").strip()
    align = (style_dict.get("align") or "").strip().lower()

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
    if align in ("left", "center", "right"):
        p.alignment = {"left": 0, "center": 1, "right": 2}[align]

    font_size = style_dict.get("font_size")
    try:
        if font_size not in (None, ""):
            fs = max(8, min(72, int(font_size)))
            p.fontSize = fs
            p.leading = max(10, int(fs * 1.25))
    except Exception:
        pass

    return p


def _apply_text_markup(text: str, style_dict: dict[str, Any]) -> str:
    out = text or ""
    if style_dict.get("underline"):
        out = f"<u>{out}</u>"
    if style_dict.get("italic"):
        out = f"<i>{out}</i>"
    if style_dict.get("bold"):
        out = f"<b>{out}</b>"
    return out


# -----------------------------
# Page bands drawing
# -----------------------------


def _flows_height(flows: list[Any], width: float) -> float:
    h = 0.0
    for f in flows or []:
        try:
            _, fh = f.wrap(width, 10_000)
            h += float(fh)
        except Exception:
            # Spacer doesn't always implement wrap nicely; ignore
            try:
                h += float(getattr(f, "height", 0) or 0)
            except Exception:
                pass
    return h


def _draw_page_band(c: Canvas, doc: SimpleDocTemplate, flows: list[Any], *, where: str, base_margin: float):
    if not flows:
        return

    page_w, page_h = doc.pagesize
    x = doc.leftMargin
    width = doc.width

    # draw from top down
    if where == "top":
        y = page_h - base_margin
        for f in flows:
            try:
                fw, fh = f.wrap(width, 10_000)
                y -= fh
                f.drawOn(c, x, y)
                # small gap
                y -= 2
            except Exception:
                continue

    # draw from bottom up (still preserve order top->bottom within the band)
    elif where == "bottom":
        total = _flows_height(flows, width)
        y = base_margin + total
        for f in flows:
            try:
                fw, fh = f.wrap(width, 10_000)
                y -= fh
                f.drawOn(c, x, y)
                y -= 2
            except Exception:
                continue


class _NumberedCanvas(Canvas):
    """Canvas that knows total page count, enabling 'Page X / Y'."""

    def __init__(self, *args, page_label: str, draw_page_numbers: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []
        self._page_label = page_label
        self._draw = bool(draw_page_numbers)

    def showPage(self):  # noqa: N802
        self._saved_page_states.append(dict(self.__dict__))
        super().showPage()

    def save(self):  # noqa: A003
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._draw:
                self._draw_page_number(num_pages)
            super().showPage()
        super().save()

    def _draw_page_number(self, page_count: int):
        page = self._pageNumber
        label = self._page_label or "Page {page} / {pages}"
        txt = label.replace("{page}", str(page)).replace("{pages}", str(page_count))

        self.saveState()
        self.setFont("Helvetica", 8)
        # centered at bottom
        w, h = self._pagesize
        self.drawCentredString(w / 2.0, 10, txt)
        self.restoreState()


# -----------------------------
# Helpers
# -----------------------------


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

    desired_w = max_width
    if width_spec:
        w = width_spec.strip()
        if w.endswith("px"):
            try:
                px = float(w[:-2].strip())
                desired_w = min(max_width, px * 0.75)  # px->pt approx
            except Exception:
                pass
        elif w.endswith("%"):
            try:
                pct = float(w[:-1].strip()) / 100.0
                desired_w = max(40, min(max_width, max_width * pct))
            except Exception:
                pass

    scale = desired_w / float(iw) if iw else 1.0
    desired_h = float(ih) * scale if ih else 120.0

    bio.seek(0)
    return Image(bio, width=desired_w, height=desired_h)


def _download_image(url: str, *, max_bytes: int = 2_000_000) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AUDELA-ReportBuilder/2.0",
            "Accept": "image/*,*/*;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("image too large")
        return data


def _safe_ident(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        raise ValueError("empty identifier")
    parts = raw.split(".")
    for p in parts:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", p):
            raise ValueError("invalid identifier")
    return ".".join(parts)


def _find_col_index(cols: list[Any], name: str) -> int:
    needle = str(name or "").strip()
    if not needle:
        return -1
    for i, c in enumerate(cols or []):
        if str(c) == needle:
            return i
    low = needle.lower()
    for i, c in enumerate(cols or []):
        if str(c).lower() == low:
            return i
    return -1


def _sort_rows(rows: list[list[Any]], idx: int, desc: bool) -> list[list[Any]]:
    if idx < 0:
        return rows

    def key_fn(r: list[Any]):
        v = r[idx] if isinstance(r, (list, tuple)) and idx < len(r) else None
        if v is None:
            return (1, "")
        if isinstance(v, (int, float)):
            return (0, float(v))
        s = str(v)
        try:
            return (0, float(s))
        except Exception:
            return (0, s.lower())

    try:
        return sorted(rows, key=key_fn, reverse=desc)
    except Exception:
        return rows


def _coalesce_detail_data_rowsets(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(blocks or []):
        b = dict(blocks[i]) if isinstance(blocks[i], dict) else {}
        btype = (b.get("type") or "").lower()
        if btype != "data_field":
            out.append(b)
            i += 1
            continue

        cfg0 = b.get("config") if isinstance(b.get("config"), dict) else {}
        bind0 = (cfg0.get("binding") or {}) if isinstance(cfg0.get("binding"), dict) else {}
        src0 = (bind0.get("source") or "").strip().lower()
        fld0 = str(bind0.get("field") or "").strip()
        if src0 not in ("question", "table") or not fld0:
            out.append(b)
            i += 1
            continue

        base_key = f"{src0}:{bind0.get('question_id') if src0 == 'question' else bind0.get('table')}"
        run: list[dict[str, Any]] = [b]
        j = i + 1
        while j < len(blocks or []):
            nb = dict(blocks[j]) if isinstance(blocks[j], dict) else {}
            ntype = (nb.get("type") or "").lower()
            if ntype != "data_field":
                break
            ncfg = nb.get("config") if isinstance(nb.get("config"), dict) else {}
            nbind = (ncfg.get("binding") or {}) if isinstance(ncfg.get("binding"), dict) else {}
            nsrc = (nbind.get("source") or "").strip().lower()
            nfield = str(nbind.get("field") or "").strip()
            if nsrc not in ("question", "table") or not nfield:
                break
            nkey = f"{nsrc}:{nbind.get('question_id') if nsrc == 'question' else nbind.get('table')}"
            if nkey != base_key:
                break
            run.append(nb)
            j += 1

        if len(run) >= 2:
            cols_meta = []
            for rb in run:
                rcfg = rb.get("config") if isinstance(rb.get("config"), dict) else {}
                rbind = (rcfg.get("binding") or {}) if isinstance(rcfg.get("binding"), dict) else {}
                rst = rb.get("style") if isinstance(rb.get("style"), dict) else {}
                cols_meta.append({
                    "title": str(rb.get("title") or "").strip() or str(rbind.get("field") or ""),
                    "field": str(rbind.get("field") or "").strip(),
                    "format": str(rcfg.get("format") or "").strip(),
                    "empty_text": str(rcfg.get("empty_text") or ""),
                    "group_key": bool(rcfg.get("group_key")),
                    "group_label": str(rcfg.get("group_label") or "Groupe: {group}"),
                    "style": {
                        "color": str(rst.get("color") or "").strip(),
                        "background": str(rst.get("background") or "").strip(),
                        "align": str(rst.get("align") or "").strip().lower(),
                        "font_size": str(rst.get("font_size") or "").strip(),
                        "bold": bool(rst.get("bold")),
                        "italic": bool(rst.get("italic")),
                        "underline": bool(rst.get("underline")),
                    },
                })
            rowset = {
                "type": "data_rowset",
                "title": str(run[0].get("title") or "").strip(),
                "config": {
                    "binding": {
                        "source": src0,
                        "question_id": bind0.get("question_id"),
                        "table": bind0.get("table"),
                    }
                },
                "columns_meta": cols_meta,
            }
            out.append(rowset)
            i = j
            continue

        out.append(b)
        i += 1

    return out


def _font_name_from_style(style: dict[str, Any]) -> str:
    bold = bool(style.get("bold"))
    italic = bool(style.get("italic"))
    if bold and italic:
        return "Helvetica-BoldOblique"
    if bold:
        return "Helvetica-Bold"
    if italic:
        return "Helvetica-Oblique"
    return "Helvetica"


def _apply_column_styles_to_table(tbl: Table, col_styles: list[dict[str, Any]]) -> None:
    cmds: list[tuple] = []
    for cidx, st in enumerate(col_styles or []):
        if not isinstance(st, dict):
            continue

        align = str(st.get("align") or "").strip().upper()
        if align in ("LEFT", "CENTER", "RIGHT"):
            cmds.append(("ALIGN", (cidx, 0), (cidx, -1), align))

        font_name = _font_name_from_style(st)
        cmds.append(("FONTNAME", (cidx, 0), (cidx, -1), font_name))

        fsz = st.get("font_size")
        try:
            if fsz not in (None, ""):
                fs = max(7, min(30, int(fsz)))
                cmds.append(("FONTSIZE", (cidx, 0), (cidx, -1), fs))
        except Exception:
            pass

        color = str(st.get("color") or "").strip()
        if color:
            try:
                cmds.append(("TEXTCOLOR", (cidx, 0), (cidx, -1), colors.HexColor(color)))
            except Exception:
                pass

        bg = str(st.get("background") or "").strip()
        if bg:
            try:
                cmds.append(("BACKGROUND", (cidx, 1), (cidx, -1), colors.HexColor(bg)))
            except Exception:
                pass

        if bool(st.get("underline")):
            cmds.append(("LINEBELOW", (cidx, 1), (cidx, -1), 0.25, colors.HexColor("#777777")))

    if cmds:
        tbl.setStyle(TableStyle(cmds))


def _normalize_table_data(data: list[Any]) -> list[list[Any]]:
    rows_in = data if isinstance(data, list) else []
    rows: list[list[Any]] = []
    for r in rows_in:
        if isinstance(r, (list, tuple)):
            rows.append(list(r))
        else:
            rows.append([r])

    if not rows:
        return [[""]]

    max_cols = max((len(r) for r in rows), default=0)
    if max_cols <= 0:
        return [[""]]

    norm: list[list[Any]] = []
    for r in rows:
        rr = list(r)
        if len(rr) < max_cols:
            rr.extend([""] * (max_cols - len(rr)))
        elif len(rr) > max_cols:
            rr = rr[:max_cols]
        norm.append(rr)
    return norm


def _safe_table(data: list[Any], *, repeat_rows: int = 0) -> Table:
    safe_data = _normalize_table_data(data)
    rr = max(0, min(int(repeat_rows or 0), len(safe_data) - 1))
    return Table(safe_data, repeatRows=rr)


def _apply_zebra_to_table(tbl: Table, *, enabled: bool) -> None:
    if not enabled:
        return
    nrows = int(getattr(tbl, "_nrows", 0) or 0)
    if nrows <= 2:
        return
    cmds: list[tuple] = []
    for r in range(1, nrows):
        if r % 2 == 0:
            cmds.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#fafafa")))
    if cmds:
        tbl.setStyle(TableStyle(cmds))


def _resolve_data_binding_value(bind: dict[str, Any], source: Any, tenant_id: int, questions_by_id: dict[int, Any]) -> str:
    source_kind = (bind.get("source") or "").strip().lower()
    if source_kind == "question":
        qid = int(bind.get("question_id") or 0)
        field = str(bind.get("field") or "").strip()
        q = questions_by_id.get(qid)
        if not q:
            return ""
        res = execute_sql(source, q.sql_text or "", {"tenant_id": tenant_id}, row_limit=1)
        cols = res.get("columns") or []
        rows = res.get("rows") or []
        if not rows:
            return ""
        idx = -1
        for i, c in enumerate(cols):
            if str(c) == field:
                idx = i
                break
        if idx < 0:
            for i, c in enumerate(cols):
                if str(c).lower() == field.lower():
                    idx = i
                    break
        if idx < 0:
            return ""
        row0 = rows[0] if isinstance(rows[0], (list, tuple)) else []
        return _format_cell(row0[idx] if idx < len(row0) else "", decimals=None)

    if source_kind == "table":
        table_name = _safe_ident(bind.get("table") or "")
        field_name = _safe_ident(bind.get("field") or "")
        sql = f"SELECT {field_name} FROM {table_name} LIMIT 1"
        res = execute_sql(source, sql, {"tenant_id": tenant_id}, row_limit=1)
        rows = res.get("rows") or []
        if not rows:
            return ""
        row0 = rows[0] if isinstance(rows[0], (list, tuple)) else []
        return _format_cell(row0[0] if row0 else "", decimals=None)

    return ""


def _apply_bound_format(value: Any, fmt: Any) -> str:
    raw = "" if value is None else str(value)
    f = str(fmt or "").strip()
    if not f:
        return raw
    if f.startswith(".") and len(f) >= 3 and f.endswith("f"):
        try:
            return format(float(raw), f)
        except Exception:
            return raw
    return raw


def _markdown_to_text(md: str) -> str:
    s = md or ""
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


def _format_date(d: date | datetime, fmt: str) -> str:
    """Format date/datetime using a simple Crystal-like pattern (dd/MM/yyyy HH:mm:ss)."""
    fmt = (fmt or "").strip() or "dd/MM/yyyy"
    # map common tokens to strftime
    m = fmt
    m = m.replace("yyyy", "%Y")
    m = m.replace("MM", "%m")
    m = m.replace("dd", "%d")
    m = m.replace("HH", "%H")
    m = m.replace("mm", "%M")
    m = m.replace("ss", "%S")
    try:
        if isinstance(d, datetime):
            return d.strftime(m)
        return datetime(d.year, d.month, d.day).strftime(m)
    except Exception:
        return str(d)


def _format_cell(v: Any, *, decimals: int | None) -> str:
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        # default date formatting for cells
        return _format_date(v, "dd/MM/yyyy")

    # Decimal, int, float
    if isinstance(v, Decimal):
        try:
            if decimals is not None:
                return f"{float(v):.{decimals}f}"
            return str(v)
        except Exception:
            return str(v)

    if isinstance(v, (int, float)):
        if decimals is not None:
            try:
                return f"{float(v):.{decimals}f}"
            except Exception:
                return str(v)
        return str(v)

    return str(v)
