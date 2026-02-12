from __future__ import annotations

"""Statistics module.

This service provides:
- Local, deterministic computations (descriptive stats, correlation, linear regression, Monte Carlo).
- A PDF export renderer (ReportLab) for the latest statistics report.

The goal is to keep dependencies minimal (no pandas/numpy).
"""

import math
import random
from io import BytesIO
from statistics import mean, median
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


# ----------------------------
# Parsing / formatting helpers
# ----------------------------
def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).strip()
        if not s:
            return None

        # Common null-like strings
        if s.lower() in {"null", "none", "nan", "n/a", "-"}:
            return None

        # Remove percent sign (keep numeric part)
        if s.endswith("%"):
            s = s[:-1].strip()

        # Remove spaces (incl. non-breaking)
        s = s.replace("\u00a0", " ").replace(" ", "")

        # Handle thousand separators for both locales:
        # - EU: 1.234,56  -> 1234.56
        # - US: 1,234.56  -> 1234.56
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                # comma is decimal separator
                s = s.replace(".", "")
                s = s.replace(",", ".")
            else:
                # dot is decimal separator
                s = s.replace(",", "")
        else:
            # Only comma present => treat as decimal separator
            if "," in s and "." not in s:
                s = s.replace(",", ".")
            # Only dot present => already ok

        return float(s)
    except Exception:
        return None


def _fmt(v: Any) -> str:
    """Always format numeric values with 2 decimals."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return ""
    if isinstance(v, int):
        return str(v)
    try:
        fv = float(v)
        if not math.isfinite(fv):
            return ""
        return f"{fv:.2f}"
    except Exception:
        return str(v)


def _fmt_pct(p: Any) -> str:
    """Format probability (0..1) as percent with 2 decimals."""
    if p is None:
        return ""
    try:
        fp = float(p)
        if not math.isfinite(fp):
            return ""
        return f"{(fp * 100.0):.2f}%"
    except Exception:
        return str(p)


def _escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ----------------------------
# Math/stat helpers
# ----------------------------
def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


def _stdev(vals: list[float]) -> float | None:
    n = len(vals)
    if n < 2:
        return None
    m = mean(vals)
    var = sum((x - m) ** 2 for x in vals) / (n - 1)
    return math.sqrt(var)


def _skewness(vals: list[float]) -> float | None:
    n = len(vals)
    if n < 3:
        return None
    m = mean(vals)
    s = _stdev(vals)
    if not s or s == 0:
        return None
    return (n / ((n - 1) * (n - 2))) * sum(((x - m) / s) ** 3 for x in vals)


def _kurtosis_excess(vals: list[float]) -> float | None:
    n = len(vals)
    if n < 4:
        return None
    m = mean(vals)
    s = _stdev(vals)
    if not s or s == 0:
        return None
    m4 = sum(((x - m) / s) ** 4 for x in vals)
    # Excess kurtosis (Fisher)
    return (n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))) * m4 - (3 * (n - 1) ** 2 / ((n - 2) * (n - 3)))


def _pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    mx, my = mean(x), mean(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return None
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return cov / (sx * sy)


def _linear_regression(x: list[float], y: list[float]) -> dict[str, Any] | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    mx, my = mean(x), mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    if sxx == 0:
        return None
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    slope = sxy / sxx
    intercept = my - slope * mx
    # r^2
    ss_tot = sum((b - my) ** 2 for b in y)
    ss_res = sum((b - (slope * a + intercept)) ** 2 for a, b in zip(x, y))
    r2 = None
    if ss_tot != 0:
        r2 = 1 - (ss_res / ss_tot)
    return {"slope": slope, "intercept": intercept, "r2": r2}


def _histogram(vals: list[float], bins: int = 12) -> dict[str, Any]:
    if not vals:
        return {"bins": [], "counts": []}
    vmin, vmax = min(vals), max(vals)
    if vmin == vmax:
        return {"bins": [f"{vmin:.2f}"], "counts": [len(vals)], "min": vmin, "max": vmax}
    step = (vmax - vmin) / bins
    counts = [0] * bins
    for v in vals:
        idx = int((v - vmin) / step)
        if idx == bins:
            idx = bins - 1
        counts[idx] += 1
    labels = [f"{(vmin + i * step):.2f}–{(vmin + (i + 1) * step):.2f}" for i in range(bins)]
    return {"bins": labels, "counts": counts, "min": vmin, "max": vmax}


def _numeric_series_for_column(rows: list[list[Any]], col_idx: int) -> list[float]:
    vals: list[float] = []
    for r in rows:
        if col_idx >= len(r):
            continue
        fv = _to_float(r[col_idx])
        if fv is None:
            continue
        vals.append(fv)
    return vals


def _paired_numeric_series(rows: list[list[Any]], x_idx: int, y_idx: int) -> tuple[list[float], list[float]]:
    x: list[float] = []
    y: list[float] = []
    for r in rows:
        if x_idx >= len(r) or y_idx >= len(r):
            continue
        fx = _to_float(r[x_idx])
        fy = _to_float(r[y_idx])
        if fx is None or fy is None:
            continue
        x.append(fx)
        y.append(fy)
    return x, y


def _is_non_null_like(val: Any) -> bool:
    if val is None:
        return False
    try:
        s = str(val).strip()
        return s != "" and s.lower() not in {"null", "none", "nan", "n/a", "-"}
    except Exception:
        return True


# ----------------------------
# Main analysis
# ----------------------------
def run_statistics_analysis(result: dict[str, Any]) -> dict[str, Any]:
    """Compute statistics from a query result {columns, rows}.

    Output is JSON-serializable and designed to be rendered by the UI.
    """

    cols: list[str] = [str(c) for c in (result.get("columns") or [])]
    rows: list[list[Any]] = result.get("rows") or []

    numeric_cols: list[dict[str, Any]] = []
    numeric_idx: list[int] = []

    for i, c in enumerate(cols):
        series = _numeric_series_for_column(rows, i)

        non_null = sum(1 for r in rows if i < len(r) and _is_non_null_like(r[i]))
        if non_null == 0:
            continue
        if len(series) < 2:
            continue
        if len(series) / max(1, non_null) < 0.5:
            continue

        series_sorted = sorted(series)
        st = _stdev(series_sorted)
        entry = {
            "name": c,
            "count": len(series_sorted),
            "mean": mean(series_sorted),
            "median": median(series_sorted),
            "std": st,
            "min": series_sorted[0],
            "max": series_sorted[-1],
            "p5": _percentile(series_sorted, 5),
            "p95": _percentile(series_sorted, 95),
            "skew": _skewness(series_sorted),
            "kurtosis_excess": _kurtosis_excess(series_sorted),
            "histogram": _histogram(series_sorted, bins=12),
        }
        numeric_cols.append(entry)
        numeric_idx.append(i)

    # Correlation matrix for numeric columns (up to 10)
    corr = None
    corr_cols = [cols[i] for i in numeric_idx[:10]]
    if len(corr_cols) >= 2:
        matrix: list[list[float | None]] = []
        for a in corr_cols:
            rowv = []
            ia = cols.index(a)
            for b in corr_cols:
                ib = cols.index(b)
                xa: list[float] = []
                yb: list[float] = []
                for r in rows:
                    if ia >= len(r) or ib >= len(r):
                        continue
                    fa = _to_float(r[ia])
                    fb = _to_float(r[ib])
                    if fa is None or fb is None:
                        continue
                    xa.append(fa)
                    yb.append(fb)
                rowv.append(_pearson(xa, yb))
            matrix.append(rowv)
        corr = {"columns": corr_cols, "matrix": matrix}

    # ----------------------------
    # Linear regression for ALL numeric "value" columns
    # ----------------------------
    regressions: list[dict[str, Any]] = []

    if len(numeric_idx) >= 2:
        # X is the first numeric column; Y is each remaining numeric column
        x_idx = numeric_idx[0]
        x_name = cols[x_idx]
        for y_idx in numeric_idx[1:]:
            y_name = cols[y_idx]
            x, y = _paired_numeric_series(rows, x_idx, y_idx)
            lr = _linear_regression(x, y)
            if not lr:
                continue
            pts = [[x[i], y[i]] for i in range(min(len(x), 400))]
            regressions.append(
                {
                    "x": x_name,
                    "y": y_name,
                    "n": len(x),
                    "points": pts,
                    **lr,
                }
            )
    elif len(numeric_idx) == 1:
        # Only one numeric column: regression vs row index (trend)
        y_idx = numeric_idx[0]
        y_name = cols[y_idx]
        x: list[float] = []
        y: list[float] = []
        for i, r in enumerate(rows):
            if y_idx >= len(r):
                continue
            fy = _to_float(r[y_idx])
            if fy is None:
                continue
            x.append(float(i + 1))  # 1-based index
            y.append(fy)
        lr = _linear_regression(x, y)
        if lr:
            pts = [[x[i], y[i]] for i in range(min(len(x), 400))]
            regressions.append(
                {
                    "x": "row_index",
                    "y": y_name,
                    "n": len(x),
                    "points": pts,
                    **lr,
                }
            )

    reg_compat = regressions[0] if regressions else None

    # ----------------------------
    # Monte Carlo for ALL numeric columns
    # ----------------------------
    rng = random.Random(42)  # deterministic
    monte_carlos: list[dict[str, Any]] = []

    for base in numeric_cols:
        mu = base.get("mean")
        sd = base.get("std")
        if not isinstance(mu, (int, float)):
            continue
        if not isinstance(sd, (int, float)):
            continue
        if not sd or sd <= 0:
            continue

        sims = [rng.gauss(float(mu), float(sd)) for _ in range(5000)]
        sims.sort()
        mc = {
            "column": base["name"],
            "n": len(sims),
            "mean": mean(sims),
            "p5": _percentile(sims, 5),
            "p50": _percentile(sims, 50),
            "p95": _percentile(sims, 95),
            "prob_lt_0": sum(1 for v in sims if v < 0) / len(sims),
        }
        monte_carlos.append(mc)

    mc_compat = monte_carlos[0] if monte_carlos else None

    # Gauges: mean normalized vs P95 (fallback max) for the first numeric column
    gauges: list[dict[str, Any]] = []
    if numeric_cols:
        base = numeric_cols[0]
        base_mean = base.get("mean")
        base_p95 = base.get("p95")
        base_max = base.get("max")

        denom = base_p95 if isinstance(base_p95, (int, float)) and base_p95 not in (0, 0.0) else base_max
        value = None
        if isinstance(base_mean, (int, float)) and isinstance(denom, (int, float)) and denom not in (0, 0.0):
            try:
                raw = (float(base_mean) / float(denom)) * 100.0
                value = max(0.0, min(100.0, raw))
                value = round(value, 2)  # 2 decimals
            except Exception:
                value = None

        gauges.append(
            {
                "title": f"Nível médio — {base.get('name', '')} (mean vs P95)",
                "type": "gauge_mean_p95",
                "column": base.get("name"),
                "mean": base_mean,
                "p95": base_p95,
                "max": base_max,
                "value": value,
                "echarts_option": {
                    "series": [
                        {
                            "type": "gauge",
                            "startAngle": 200,
                            "endAngle": -20,
                            "min": 0,
                            "max": 100,
                            "splitNumber": 5,
                            "progress": {"show": True, "width": 14},
                            "axisLine": {"lineStyle": {"width": 14}},
                            "axisTick": {"show": True},
                            "splitLine": {"show": True, "length": 12},
                            "axisLabel": {"distance": 18},
                            "pointer": {"length": "60%", "width": 5},
                            "anchor": {"show": True, "showAbove": True, "size": 12},
                            "title": {"show": True, "offsetCenter": [0, "60%"], "fontSize": 12},
                            "detail": {
                                "valueAnimation": True,
                                "formatter": "{value}%",
                                "offsetCenter": [0, "25%"],
                                "fontSize": 18,
                            },
                            "data": [
                                {
                                    "value": value if value is not None else 0,
                                    "name": "mean / P95",
                                }
                            ],
                        }
                    ]
                },
            }
        )

    # ECharts options (client-side rendering)
    charts: list[dict[str, Any]] = []

    # Histograms
    for nc in numeric_cols[:3]:
        h = nc.get("histogram") or {}
        charts.append(
            {
                "title": f"Distribuição (histograma) — {nc['name']}",
                "type": "histogram",
                "echarts_option": {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": h.get("bins") or [], "axisLabel": {"interval": 1, "rotate": 30}},
                    "yAxis": {"type": "value"},
                    "series": [{"type": "bar", "data": h.get("counts") or []}],
                },
            }
        )

    # Correlation heatmap
    if corr and len(corr.get("columns") or []) >= 2:
        cols_corr = corr["columns"]
        mat = corr["matrix"]
        data = []
        for i in range(len(cols_corr)):
            for j in range(len(cols_corr)):
                v = mat[i][j]
                if v is None:
                    continue
                data.append([j, i, round(float(v), 2)])  # 2 decimals
        charts.append(
            {
                "title": "Correlação (Pearson) — heatmap",
                "type": "correlation",
                "echarts_option": {
                    "tooltip": {"position": "top"},
                    "grid": {"height": "60%", "top": "10%"},
                    "xAxis": {"type": "category", "data": cols_corr},
                    "yAxis": {"type": "category", "data": cols_corr},
                    "visualMap": {
                        "min": -1,
                        "max": 1,
                        "calculable": True,
                        "orient": "horizontal",
                        "left": "center",
                        "bottom": "0%",
                    },
                    "series": [
                        {
                            "name": "corr",
                            "type": "heatmap",
                            "data": data,
                            "label": {"show": False},
                            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"}},
                        }
                    ],
                },
            }
        )

    # Regression charts (show only first 2 to keep UI light)
    for reg in regressions[:2]:
        pts = reg.get("points") or []
        xs = [p[0] for p in pts] if pts else []
        x_min = min(xs) if xs else 0
        x_max = max(xs) if xs else 1
        slope = float(reg.get("slope") or 0)
        intercept = float(reg.get("intercept") or 0)
        line = [[x_min, slope * x_min + intercept], [x_max, slope * x_max + intercept]]
        charts.append(
            {
                "title": f"Regressão linear — {reg['y']} vs {reg['x']}",
                "type": "regression",
                "echarts_option": {
                    "tooltip": {"trigger": "item"},
                    "xAxis": {"type": "value", "name": reg["x"]},
                    "yAxis": {"type": "value", "name": reg["y"]},
                    "series": [
                        {"type": "scatter", "symbolSize": 6, "data": pts},
                        {"type": "line", "showSymbol": False, "data": line},
                    ],
                },
            }
        )

    return {
        "summary": {
            "rows": len(rows),
            "columns": len(cols),
            "numeric_columns": len(numeric_cols),
        },
        "numeric": numeric_cols,
        "correlation": corr,
        # new multi outputs
        "regressions": regressions,
        "monte_carlos": monte_carlos,
        # backwards-compat
        "regression": reg_compat,
        "monte_carlo": mc_compat,
        "gauges": gauges,
        "charts": charts,
    }


# ----------------------------
# PDF export
# ----------------------------
def _kv_table(title: str, pairs: Iterable[tuple[str, Any]]) -> Table:
    data = [["Campo", "Valor"]]
    for k, v in pairs:
        data.append([str(k), "" if v is None else str(v)])
    tbl = Table(data, colWidths=[160, 360])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tbl


def stats_report_to_pdf_bytes(
    *,
    title: str,
    source: Any,
    sql_text: str,
    result: dict[str, Any],
    stats: dict[str, Any],
    ai: dict[str, Any] | None = None,
) -> bytes:
    """Render a stats report to PDF bytes (ReportLab).

    Charts are not embedded (client-side ECharts). Instead we include the key numeric tables
    plus an executive summary (AI if available).
    """

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
        title=title or "Statistics",
    )

    styles = getSampleStyleSheet()
    story: list[Any] = []

    story.append(Paragraph(title or "Statistics", styles["Title"]))
    story.append(Spacer(1, 8))

    gauge_val = ((stats.get("gauges") or [{}])[0] or {}).get("value")
    story.append(
        _kv_table(
            "Meta",
            [
                ("Fonte", getattr(source, "name", "")),
                ("Tipo", getattr(source, "type", "")),
                ("Linhas (amostra)", (stats.get("summary") or {}).get("rows")),
                ("Colunas", (stats.get("summary") or {}).get("columns")),
                ("Colunas numéricas", (stats.get("summary") or {}).get("numeric_columns")),
                ("Gauge (mean/P95)", _fmt(gauge_val)),
            ],
        )
    )
    story.append(Spacer(1, 10))

    if ai and isinstance(ai, dict) and ai.get("analysis"):
        story.append(Paragraph("Resumo executivo (IA)", styles["Heading2"]))
        story.append(Spacer(1, 4))
        text = str(ai.get("analysis"))
        story.append(Paragraph(text[:4000].replace("\n", "<br/>"), styles["BodyText"]))
        story.append(Spacer(1, 10))

    story.append(Paragraph("Estatísticas descritivas", styles["Heading2"]))
    story.append(Spacer(1, 6))

    numeric = stats.get("numeric") or []
    data = [["Coluna", "count", "mean", "std", "min", "p5", "median", "p95", "max"]]
    for n in numeric[:20]:
        data.append(
            [
                n.get("name"),
                n.get("count"),
                _fmt(n.get("mean")),
                _fmt(n.get("std")),
                _fmt(n.get("min")),
                _fmt(n.get("p5")),
                _fmt(n.get("median")),
                _fmt(n.get("p95")),
                _fmt(n.get("max")),
            ]
        )

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
    story.append(Spacer(1, 10))

    # Regressions (multi)
    regressions = stats.get("regressions") or ([] if not stats.get("regression") else [stats.get("regression")])
    if regressions:
        story.append(Paragraph("Regressão linear (múltiplas)", styles["Heading2"]))
        story.append(Spacer(1, 6))

        reg_data = [["X", "Y", "N", "Slope", "Intercept", "R²"]]
        for r in regressions[:20]:
            reg_data.append(
                [
                    r.get("x"),
                    r.get("y"),
                    r.get("n"),
                    _fmt(r.get("slope")),
                    _fmt(r.get("intercept")),
                    _fmt(r.get("r2")),
                ]
            )

        reg_tbl = Table(reg_data, repeatRows=1)
        reg_tbl.setStyle(
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
        story.append(reg_tbl)
        story.append(Spacer(1, 10))

    # Monte Carlo (multi)
    monte_carlos = stats.get("monte_carlos") or ([] if not stats.get("monte_carlo") else [stats.get("monte_carlo")])
    if monte_carlos:
        story.append(Paragraph("Monte Carlo (normal aproximada) — múltiplas colunas", styles["Heading2"]))
        story.append(Spacer(1, 6))

        mc_data = [["Coluna", "Simulações", "Mean", "P5", "P50", "P95", "Prob < 0"]]
        for mc in monte_carlos[:20]:
            mc_data.append(
                [
                    mc.get("column"),
                    mc.get("n"),
                    _fmt(mc.get("mean")),
                    _fmt(mc.get("p5")),
                    _fmt(mc.get("p50")),
                    _fmt(mc.get("p95")),
                    _fmt_pct(mc.get("prob_lt_0")),
                ]
            )

        mc_tbl = Table(mc_data, repeatRows=1)
        mc_tbl.setStyle(
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
        story.append(mc_tbl)
        story.append(Spacer(1, 10))

    story.append(Paragraph("SQL (executado)", styles["Heading2"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<pre>%s</pre>" % _escape((sql_text or "")[:4000]), styles["BodyText"]))

    doc.build(story)
    return buf.getvalue()
