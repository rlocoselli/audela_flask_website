from __future__ import annotations

"""Excel (XLSX) export helpers.

This module is intentionally dependency-light (openpyxl only).

It produces:
- a "Data" sheet with headers, frozen panes, and auto-filter
- optionally a "Chart" sheet with a simple bar chart when the dataset
  looks like (category, numeric)
"""

from io import BytesIO
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter


def _is_number(v: Any) -> bool:
    try:
        if v is None:
            return False
        float(v)
        return True
    except Exception:
        return False


def _safe_cell(v: Any) -> Any:
    # openpyxl handles numbers, strings, dates. For safety, stringify complex types.
    if v is None:
        return None
    if isinstance(v, (int, float, str)):
        return v
    return str(v)


def table_to_xlsx_bytes(
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    *,
    add_chart: bool = True,
    chart_title: str | None = None,
    top_n: int = 15,
) -> bytes:
    """Create an .xlsx file from a tabular dataset.

    Chart behavior (best effort):
    - If there are at least 2 columns, and the 2nd column is mostly numeric,
      create a bar chart using col1 as category and col2 as value.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"

    # Title row (optional, but nice)
    title = (title or "Export").strip() or "Export"
    ws["A1"].value = title
    ws["A1"].font = Font(size=14, bold=True)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(1, len(columns)))
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

    # Header
    header_row = 3
    for c_idx, col in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=c_idx)
        cell.value = str(col)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Data
    max_rows = 200000  # practical safety
    rows = rows[:max_rows]
    for r_idx, r in enumerate(rows, start=header_row + 1):
        for c_idx, v in enumerate(r[: len(columns)], start=1):
            ws.cell(row=r_idx, column=c_idx).value = _safe_cell(v)

    # Freeze + filter
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    if columns:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(columns))}{header_row + len(rows)}"

    # Column widths (best effort)
    for i, col in enumerate(columns, start=1):
        width = min(45, max(10, len(str(col)) + 2))
        ws.column_dimensions[get_column_letter(i)].width = width

    # Optional chart
    if add_chart and len(columns) >= 2 and rows:
        # Determine if 2nd column is numeric enough
        sample = rows[: min(50, len(rows))]
        numeric_hits = sum(1 for r in sample if len(r) >= 2 and _is_number(r[1]))
        if numeric_hits >= max(5, int(0.6 * len(sample))):
            ws_chart = wb.create_sheet(title="Chart")
            ws_chart["A1"].value = chart_title or "Chart"
            ws_chart["A1"].font = Font(size=14, bold=True)

            # Copy top N (sorted by value desc) to chart sheet for stable references
            data_pairs: list[tuple[Any, float]] = []
            for r in rows:
                if len(r) < 2:
                    continue
                if _is_number(r[1]):
                    try:
                        data_pairs.append((r[0], float(r[1])))
                    except Exception:
                        pass
            data_pairs.sort(key=lambda x: x[1], reverse=True)
            data_pairs = data_pairs[: max(1, int(top_n))]

            ws_chart["A3"].value = str(columns[0])
            ws_chart["B3"].value = str(columns[1])
            ws_chart["A3"].font = Font(bold=True)
            ws_chart["B3"].font = Font(bold=True)

            for i, (cat, val) in enumerate(data_pairs, start=4):
                ws_chart[f"A{i}"].value = _safe_cell(cat)
                ws_chart[f"B{i}"].value = val

            chart = BarChart()
            chart.type = "col"
            chart.style = 10
            chart.title = chart_title or f"{columns[1]} by {columns[0]}"
            chart.y_axis.title = str(columns[1])
            chart.x_axis.title = str(columns[0])

            data_ref = Reference(ws_chart, min_col=2, min_row=3, max_row=3 + len(data_pairs))
            cats_ref = Reference(ws_chart, min_col=1, min_row=4, max_row=3 + len(data_pairs))
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats_ref)
            chart.height = 13
            chart.width = 26
            ws_chart.add_chart(chart, "D3")

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
