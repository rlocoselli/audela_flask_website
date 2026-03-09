from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO
from typing import Iterable, List, Tuple

from ..models.finance import FinanceAccount, FinanceTransaction
from ..models.finance_ext import FinanceLiability
from ..models.finance_invoices import FinanceInvoice


def _d(x) -> Decimal:
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal("0")


def normalize_counterparty_label(value: str | None) -> str:
    text = " ".join((value or "").strip().split())
    if not text:
        return "(n/a)"

    normalized = text.upper()
    normalized = re.sub(
        r"\b(CB|CARTE|PAIEMENT|PAYMENT|ACHAT|VIR(?:EMENT)?|SEPA|PRLV|PRELEVEMENT|"
        r"POS|FACTURE|FACT|REF|REFERENCE|TRANSFERT|TRANSFER|TXN|DEBIT|CREDIT)\b",
        " ",
        normalized,
    )
    normalized = re.sub(r"\b\d{3,}\b", " ", normalized)
    normalized = re.sub(r"[^A-Z0-9 ]+", " ", normalized)
    normalized = " ".join(normalized.split())
    return normalized or text


@dataclass
class CashflowPoint:
    day: date
    inflow: Decimal
    outflow: Decimal
    net: Decimal
    balance: Decimal
    txns_net: Decimal
    financing_net: Decimal


def compute_starting_cash(accounts: Iterable[FinanceAccount]) -> Decimal:
    """Starting cash = sum of cash/bank balances (across currencies).

    Note: this is a simplified model. For multi-currency you typically need FX rates.
    """
    total = Decimal("0")
    for a in accounts:
        if (a.account_type or "").lower() in {"cash", "bank"}:
            total += _d(a.balance)
    return total


def compute_cashflow(
    transactions: Iterable[FinanceTransaction],
    start: date,
    end: date,
    starting_balance: Decimal,
    extra_events: Iterable[tuple[date, Decimal, str] | tuple[date, Decimal]] | None = None,
) -> List[CashflowPoint]:
    """Aggregate transactions into daily cashflow and compute cumulative balance."""
    # Aggregate by day
    by_day: dict[date, Tuple[Decimal, Decimal]] = {}
    by_day_txns_net: dict[date, Decimal] = {}
    by_day_financing_net: dict[date, Decimal] = {}
    for t in transactions:
        d = t.txn_date
        if d < start or d > end:
            continue
        amt = _d(t.amount)
        inflow, outflow = by_day.get(d, (Decimal("0"), Decimal("0")))
        if amt >= 0:
            inflow += amt
        else:
            outflow += (-amt)
        by_day[d] = (inflow, outflow)
        by_day_txns_net[d] = by_day_txns_net.get(d, Decimal("0")) + amt

    # Optional synthetic events (e.g. financing drawdown and installment schedule)
    if extra_events:
        for item in extra_events:
            if len(item) == 3:
                d, amt_raw, source = item
            else:
                d, amt_raw = item
                source = "financing"
            if d < start or d > end:
                continue
            amt = _d(amt_raw)
            inflow, outflow = by_day.get(d, (Decimal("0"), Decimal("0")))
            if amt >= 0:
                inflow += amt
            else:
                outflow += (-amt)
            by_day[d] = (inflow, outflow)
            if (source or "").lower() == "financing":
                by_day_financing_net[d] = by_day_financing_net.get(d, Decimal("0")) + amt
            else:
                by_day_txns_net[d] = by_day_txns_net.get(d, Decimal("0")) + amt

    pts: List[CashflowPoint] = []
    bal = _d(starting_balance)
    cur = start
    while cur <= end:
        inflow, outflow = by_day.get(cur, (Decimal("0"), Decimal("0")))
        net = inflow - outflow
        bal = bal + net
        pts.append(
            CashflowPoint(
                day=cur,
                inflow=inflow,
                outflow=outflow,
                net=net,
                balance=bal,
                txns_net=by_day_txns_net.get(cur, Decimal("0")),
                financing_net=by_day_financing_net.get(cur, Decimal("0")),
            )
        )
        cur += timedelta(days=1)
    return pts


def compute_opening_balance(
    transactions: Iterable[FinanceTransaction],
    start: date,
    as_of: date,
    current_balance: Decimal,
) -> Decimal:
    """Compute opening balance for the start date using current balance and transactions.

    Assumes current_balance reflects the balance as of `as_of` (today).
    """
    opening = _d(current_balance)
    if start <= as_of:
        net = Decimal("0")
        for t in transactions:
            if start <= t.txn_date <= as_of:
                net += _d(t.amount)
        return opening - net

    # Start date in the future: project using scheduled transactions before start
    net = Decimal("0")
    for t in transactions:
        if as_of < t.txn_date < start:
            net += _d(t.amount)
    return opening + net


def compute_nii(accounts: Iterable[FinanceAccount], horizon_days: int = 365) -> dict:
    """Compute a simple Net Interest Income estimate over a horizon.

    - Uses constant balance assumption.
    - annual_rate is a decimal (e.g. 0.05 = 5%).
    - side: asset => interest income; liability => interest expense.

    Returns: {"rows": [...], "nii_total": Decimal}
    """
    rows = []
    total = Decimal("0")
    for a in accounts:
        if not a.is_interest_bearing:
            continue
        rate = _d(a.annual_rate)
        bal = _d(a.balance)
        # daily interest
        interest = (bal * rate * Decimal(str(horizon_days))) / Decimal("365")
        sign = Decimal("1") if (a.side or "asset").lower() == "asset" else Decimal("-1")
        nii = sign * interest
        total += nii
        rows.append(
            {
                "account_id": a.id,
                "name": a.name,
                "side": a.side,
                "balance": bal,
                "rate": rate,
                "horizon_days": horizon_days,
                "nii": nii,
            }
        )
    return {"rows": rows, "nii_total": total}


_BUCKETS = [
    (0, 30, "0-30d"),
    (31, 90, "31-90d"),
    (91, 180, "91-180d"),
    (181, 365, "181-365d"),
    (366, 730, "1-2y"),
    (731, 1825, "2-5y"),
    (1826, 10_000, ">5y"),
]


def _bucket_label(days: int) -> str:
    for lo, hi, lbl in _BUCKETS:
        if lo <= days <= hi:
            return lbl
    return ">5y"


def compute_interest_rate_gaps(accounts: Iterable[FinanceAccount], as_of: date | None = None) -> dict:
    """Compute a simplified repricing/maturity gap by time bucket."""
    as_of = as_of or date.today()
    buckets: dict[str, dict[str, Decimal]] = {}

    def add(lbl: str, side: str, amount: Decimal, fallback: bool = False) -> None:
        buckets.setdefault(
            lbl,
            {
                "assets": Decimal("0"),
                "liabilities": Decimal("0"),
                "gap": Decimal("0"),
                "fallback": Decimal("0"),
            },
        )
        if side == "asset":
            buckets[lbl]["assets"] += amount
        else:
            buckets[lbl]["liabilities"] += amount
        if fallback:
            buckets[lbl]["fallback"] += amount
        buckets[lbl]["gap"] = buckets[lbl]["assets"] - buckets[lbl]["liabilities"]

    for a in accounts:
        # Fallback: accounts without dates go to 0-30d bucket
        dt = a.repricing_date or a.maturity_date
        if dt:
            days = (dt - as_of).days
            if days < 0:
                days = 0
            fallback = False
        else:
            days = 0
            fallback = True
        lbl = _bucket_label(days)
        add(lbl, (a.side or "asset").lower(), _d(a.balance), fallback=fallback)

    ordered = []
    for _, _, lbl in _BUCKETS:
        if lbl in buckets:
            ordered.append({"bucket": lbl, **buckets[lbl]})
        else:
            ordered.append(
                {
                    "bucket": lbl,
                    "assets": Decimal("0"),
                    "liabilities": Decimal("0"),
                    "gap": Decimal("0"),
                    "fallback": Decimal("0"),
                }
            )
    return {"rows": ordered}


def compute_liquidity(accounts: Iterable[FinanceAccount], horizon_days: int = 30) -> dict:
    """Compute a lightweight liquidity view.

    - Sources: cash/bank + undrawn credit lines
    - Uses: liabilities maturing within horizon (maturity_date <= horizon)

    This is NOT a regulatory LCR/NSFR model; it's an SME-friendly approximation.
    """
    as_of = date.today()
    sources_cash = Decimal("0")
    sources_lines = Decimal("0")
    uses_short_liab = Decimal("0")

    for a in accounts:
        t = (a.account_type or "").lower()
        side = (a.side or "asset").lower()
        bal = _d(a.balance)

        if t in {"cash", "bank"}:
            sources_cash += bal

        if t == "credit_line":
            limit_amt = _d(a.limit_amount)
            used = max(Decimal("0"), -bal) if side == "liability" else max(Decimal("0"), bal)
            # if stored as liability with negative balance (drawn), keep it simple
            undrawn = max(Decimal("0"), limit_amt - used)
            sources_lines += undrawn

        if side == "liability":
            dt = a.maturity_date
            if dt and (dt - as_of).days <= horizon_days:
                uses_short_liab += abs(bal)

    total_sources = sources_cash + sources_lines
    ratio = (total_sources / uses_short_liab) if uses_short_liab > 0 else None

    return {
        "as_of": as_of,
        "horizon_days": horizon_days,
        "sources_cash": sources_cash,
        "sources_lines": sources_lines,
        "uses_short_liab": uses_short_liab,
        "total_sources": total_sources,
        "liquidity_ratio": ratio,
        "net_liquidity": total_sources - uses_short_liab,
    }


def compute_basic_risk(accounts: Iterable[FinanceAccount]) -> dict:
    """Compute a few SME-friendly exposures (currency + counterparty concentration)."""
    by_ccy: dict[str, Decimal] = {}
    by_cp: dict[str, Decimal] = {}

    for a in accounts:
        ccy = (a.currency or "").upper() or "EUR"
        by_ccy[ccy] = by_ccy.get(ccy, Decimal("0")) + _d(a.balance)

        cp = (a.counterparty_ref.name if getattr(a, "counterparty_ref", None) else (a.counterparty or "").strip()) or "(n/a)"
        by_cp[cp] = by_cp.get(cp, Decimal("0")) + abs(_d(a.balance))

    ccy_rows = sorted(
        [{"currency": k, "exposure": v} for k, v in by_ccy.items()],
        key=lambda r: abs(r["exposure"]),
        reverse=True,
    )
    cp_rows = sorted(
        [{"counterparty": k, "exposure": v} for k, v in by_cp.items()],
        key=lambda r: r["exposure"],
        reverse=True,
    )

    return {"currency": ccy_rows, "counterparty": cp_rows[:10]}


def compute_risk_metrics(
    accounts: Iterable[FinanceAccount],
    transactions: Iterable[FinanceTransaction] | None = None,
    liabilities: Iterable[FinanceLiability] | None = None,
    invoices: Iterable[FinanceInvoice] | None = None,
    ifrs9_config: dict | None = None,
) -> dict:
    """Compute robust SME-friendly liquidity risk metrics: LCR, NSFR, and concentration ratios.
    
    LCR (Liquidity Coverage Ratio) = High Quality Liquid Assets / Total Net Cash Outflows (30d)
    - Target: >= 100%
    
    NSFR (Net Stable Funding Ratio) = Available Stable Funding / Required Stable Funding
    - Target: >= 100%
    
    Returns metrics for dashboard display and monitoring.
    """
    as_of = date.today()
    accounts_list = list(accounts)
    
    # ===== LCR Calculation =====
    # HQLA = High Quality Liquid Assets (cash + bank accounts with immediate access)
    hqla = Decimal("0")
    
    # Net Cash Outflows over 30 days
    net_30d_outflows = Decimal("0")
    
    # Liability maturity profile & projected outflows
    liabilities_0_30d = Decimal("0")
    liabilities_30_90d = Decimal("0")
    liabilities_total = Decimal("0")
    
    # Asset liquidity profile
    assets_illiquid = Decimal("0")
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    
    for a in accounts_list:
        t = (a.account_type or "").lower()
        side = (a.side or "asset").lower()
        bal = _d(a.balance)
        
        # Track total assets/liabilities for NSFR
        if side == "asset":
            total_assets += bal
        else:
            total_liabilities += abs(bal)
        
        # HQLA: immediate access cash and bank balances
        if t in {"cash", "bank"} and side == "asset":
            hqla += bal
        
        # Liability maturity bucketing for LCR
        if side == "liability":
            dt = a.maturity_date
            if dt:
                days_to_maturity = (dt - as_of).days
                if days_to_maturity <= 30 and days_to_maturity > 0:
                    liabilities_0_30d += abs(bal)
                elif days_to_maturity <= 90 and days_to_maturity > 30:
                    liabilities_30_90d += abs(bal)
            else:
                # No maturity date: assume stable liability (longer term)
                pass
            liabilities_total += abs(bal)
        
        # Illiquid assets (loans, receivables)
        if t in {"loan", "receivable"} and side == "asset":
            assets_illiquid += bal
    
    # Include financing registry liabilities (finance_liabilities) in maturity buckets.
    # This avoids missing denominator/short-term outflows when liabilities are tracked
    # in financing registry but not mirrored as balance-sheet liability accounts.
    for l in (liabilities or []):
        principal = _d(getattr(l, "outstanding_amount", None))
        if principal <= 0:
            principal = _d(getattr(l, "principal_amount", None))
        principal = abs(principal)
        if principal <= 0:
            continue

        total_liabilities += principal
        liabilities_total += principal

        dt = getattr(l, "maturity_date", None)
        if dt:
            days_to_maturity = (dt - as_of).days
            if days_to_maturity <= 30:
                liabilities_0_30d += principal
            elif days_to_maturity <= 90:
                liabilities_30_90d += principal

    # For 30-day horizon: assume liability outflows + some emergency withdrawal allowance
    # SME approximation: assume 10% of HQLA must be held as buffer for operational needs
    # and 100% of liabilities maturing in 30d must be paid
    emergency_buffer = hqla * Decimal("0.10") if hqla > 0 else Decimal("0")
    net_30d_outflows = liabilities_0_30d + emergency_buffer
    
    # LCR = HQLA / Net Outflows
    lcr = (hqla / net_30d_outflows * 100) if net_30d_outflows > 0 else Decimal("0")
    lcr_status = "healthy" if lcr >= 100 else ("caution" if lcr >= 75 else "stressed")
    
    # ===== NSFR Calculation =====
    # Available Stable Funding (ASF) = Equity + Stable Liabilities
    # For SME: assume all equity (net assets) + liabilities > 1 year
    equity = total_assets - total_liabilities
    liabilities_stable = liabilities_total - liabilities_0_30d  # longer-term liabilities
    asf = max(Decimal("0"), equity) + liabilities_stable
    
    # Required Stable Funding (RSF) = Illiquid Assets + Committed Outflows
    # For SME: assume 50% of illiquid assets + 100% of short-term commitments
    rsf = (assets_illiquid * Decimal("0.50")) + liabilities_0_30d
    
    # NSFR = ASF / RSF
    nsfr = (asf / rsf * 100) if rsf > 0 else Decimal("0")
    nsfr_status = "healthy" if nsfr >= 100 else ("caution" if nsfr >= 75 else "stressed")
    
    # ===== Concentration Ratios =====
    # Prefer transaction-based concentration (requested behavior):
    # exposure per currency/counterparty as % of total transaction volume.
    by_ccy: dict[str, Decimal] = {}
    by_cp: dict[str, Decimal] = {}
    cp_display: dict[str, str] = {}
    txns_list = list(transactions or [])

    if txns_list:
        total_txn_volume = Decimal("0")
        for t in txns_list:
            amt = abs(_d(getattr(t, "amount", None)))
            if amt <= 0:
                continue

            total_txn_volume += amt
            account = getattr(t, "account", None)
            ccy = (getattr(account, "currency", "") or "").upper() or "EUR"
            by_ccy[ccy] = by_ccy.get(ccy, Decimal("0")) + amt

            raw_cp = (
                t.counterparty_ref.name
                if getattr(t, "counterparty_ref", None)
                else (getattr(t, "counterparty", "") or "").strip()
            )
            if not raw_cp:
                raw_cp = (getattr(t, "description", "") or "").strip()

            cp = normalize_counterparty_label(raw_cp)
            cp_key = cp.casefold()
            cp_display.setdefault(cp_key, cp)
            by_cp[cp_key] = by_cp.get(cp_key, Decimal("0")) + amt

        concentration_base = total_txn_volume
    else:
        # Backward-compatible fallback when no transactions exist yet.
        for a in accounts_list:
            ccy = (a.currency or "").upper() or "EUR"
            by_ccy[ccy] = by_ccy.get(ccy, Decimal("0")) + abs(_d(a.balance))

            cp_raw = (a.counterparty_ref.name if getattr(a, "counterparty_ref", None) else (a.counterparty or "").strip())
            cp = normalize_counterparty_label(cp_raw)
            cp_key = cp.casefold()
            cp_display.setdefault(cp_key, cp)
            by_cp[cp_key] = by_cp.get(cp_key, Decimal("0")) + abs(_d(a.balance))

        concentration_base = abs(total_assets)

    ccy_rows = []
    for k, v in sorted(by_ccy.items(), key=lambda x: x[1], reverse=True):
        conc_ratio = (v / concentration_base * 100) if concentration_base > 0 else Decimal("0")
        ccy_rows.append({
            "currency": k,
            "exposure": v,
            "concentration": conc_ratio,
        })

    cp_rows = []
    for k, v in sorted(by_cp.items(), key=lambda x: x[1], reverse=True)[:10]:
        conc_ratio = (v / concentration_base * 100) if concentration_base > 0 else Decimal("0")
        cp_rows.append({
            "counterparty": cp_display.get(k, k),
            "exposure": v,
            "concentration": conc_ratio,
        })
    
    # ===== IFRS9 (SME approximation for expected credit losses) =====
    # Scope: open sales invoices are treated as receivable exposures.
    # Staging by Days Past Due (DPD):
    #   Stage 1: current or <= 30 DPD (12-month ECL proxy)
    #   Stage 2: 31-90 DPD (lifetime ECL)
    #   Stage 3: > 90 DPD (credit-impaired)
    cfg = ifrs9_config or {}
    stage_1_max_dpd = int(cfg.get("stage_1_max_dpd") or 30)
    stage_2_max_dpd = int(cfg.get("stage_2_max_dpd") or 90)
    if stage_1_max_dpd < 0:
        stage_1_max_dpd = 0
    if stage_2_max_dpd <= stage_1_max_dpd:
        stage_2_max_dpd = stage_1_max_dpd + 60

    stage_cfg = {
        "stage_1": {
            "label": "Stage 1",
            "pd": _d(cfg.get("pd_stage_1") or "2") / Decimal("100"),
            "lgd": _d(cfg.get("lgd_stage_1") or "40") / Decimal("100"),
            "dpd_min": -9999,
            "dpd_max": stage_1_max_dpd,
        },
        "stage_2": {
            "label": "Stage 2",
            "pd": _d(cfg.get("pd_stage_2") or "10") / Decimal("100"),
            "lgd": _d(cfg.get("lgd_stage_2") or "50") / Decimal("100"),
            "dpd_min": stage_1_max_dpd + 1,
            "dpd_max": stage_2_max_dpd,
        },
        "stage_3": {
            "label": "Stage 3",
            "pd": _d(cfg.get("pd_stage_3") or "35") / Decimal("100"),
            "lgd": _d(cfg.get("lgd_stage_3") or "65") / Decimal("100"),
            "dpd_min": stage_2_max_dpd + 1,
            "dpd_max": 9999,
        },
    }
    for _k in stage_cfg:
        stage_cfg[_k]["pd"] = max(Decimal("0"), min(Decimal("1"), stage_cfg[_k]["pd"]))
        stage_cfg[_k]["lgd"] = max(Decimal("0"), min(Decimal("1"), stage_cfg[_k]["lgd"]))
    ifrs9_rows: list[dict] = []
    ifrs9_by_stage: dict[str, dict] = {
        "stage_1": {"label": "Stage 1", "exposure": Decimal("0"), "ecl": Decimal("0"), "count": 0},
        "stage_2": {"label": "Stage 2", "exposure": Decimal("0"), "ecl": Decimal("0"), "count": 0},
        "stage_3": {"label": "Stage 3", "exposure": Decimal("0"), "ecl": Decimal("0"), "count": 0},
    }
    overdue_by_cp: dict[str, Decimal] = {}

    for inv in (invoices or []):
        if (getattr(inv, "invoice_type", "") or "").lower() != "sale":
            continue
        status = (getattr(inv, "status", "") or "").lower()
        if status in {"paid", "void"}:
            continue

        ead = abs(_d(getattr(inv, "total_gross", None)))
        if ead <= 0:
            continue

        due_date = getattr(inv, "due_date", None) or getattr(inv, "issue_date", None) or as_of
        dpd = max(0, (as_of - due_date).days)

        if dpd <= 30:
            stage_key = "stage_1"
        elif dpd <= 90:
            stage_key = "stage_2"
        else:
            stage_key = "stage_3"

        cfg = stage_cfg[stage_key]
        pd = cfg["pd"]
        lgd = cfg["lgd"]
        ecl = ead * pd * lgd

        cp_name = (
            getattr(getattr(inv, "counterparty", None), "name", None)
            or "(n/a)"
        )
        cp_norm = normalize_counterparty_label(cp_name)

        ifrs9_rows.append(
            {
                "invoice_number": getattr(inv, "invoice_number", None) or "-",
                "counterparty": cp_name,
                "counterparty_normalized": cp_norm,
                "status": status,
                "currency": getattr(inv, "currency", None) or "EUR",
                "due_date": due_date,
                "days_past_due": dpd,
                "stage": cfg["label"],
                "stage_key": stage_key,
                "pd": pd,
                "lgd": lgd,
                "ead": ead,
                "ecl": ecl,
            }
        )

        ifrs9_by_stage[stage_key]["exposure"] += ead
        ifrs9_by_stage[stage_key]["ecl"] += ecl
        ifrs9_by_stage[stage_key]["count"] += 1

        if dpd > 0:
            overdue_by_cp[cp_norm] = overdue_by_cp.get(cp_norm, Decimal("0")) + ead

    total_ifrs9_exposure = sum((r["ead"] for r in ifrs9_rows), Decimal("0"))
    total_ifrs9_ecl = sum((r["ecl"] for r in ifrs9_rows), Decimal("0"))
    coverage_ratio = (total_ifrs9_ecl / total_ifrs9_exposure * 100) if total_ifrs9_exposure > 0 else Decimal("0")

    overdue_cp_rows = [
        {
            "counterparty": cp,
            "exposure": amt,
            "share": (amt / total_ifrs9_exposure * 100) if total_ifrs9_exposure > 0 else Decimal("0"),
        }
        for cp, amt in sorted(overdue_by_cp.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # ===== Output Summary =====
    return {
        "as_of": as_of,
        "lcr": {
            "ratio": lcr,
            "status": lcr_status,
            "hqla": hqla,
            "net_outflows_30d": net_30d_outflows,
            "target": Decimal("100"),
        },
        "nsfr": {
            "ratio": nsfr,
            "status": nsfr_status,
            "asf": asf,
            "rsf": rsf,
            "target": Decimal("100"),
        },
        "liquidity": {
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "equity": equity,
            "liabilities_0_30d": liabilities_0_30d,
            "liabilities_30_90d": liabilities_30_90d,
            "assets_illiquid": assets_illiquid,
        },
        "concentration": {
            "currency": ccy_rows,
            "counterparty": cp_rows,
        },
        "ifrs9": {
            "open_receivables_count": len(ifrs9_rows),
            "total_exposure": total_ifrs9_exposure,
            "total_ecl": total_ifrs9_ecl,
            "coverage_ratio": coverage_ratio,
            "stages": [ifrs9_by_stage["stage_1"], ifrs9_by_stage["stage_2"], ifrs9_by_stage["stage_3"]],
            "rows": sorted(ifrs9_rows, key=lambda r: (r["days_past_due"], r["ecl"]), reverse=True),
            "overdue_counterparties": overdue_cp_rows,
        },
    }



def parse_transactions_csv(text: str) -> list[dict]:
    """Parse a CSV with columns: date, amount, description, category, counterparty.

    The separator can be ',' or ';'. Dates supported: YYYY-MM-DD, DD/MM/YYYY.
    """
    if not text:
        return []

    sample = text[:2048]
    sep = ";" if sample.count(";") > sample.count(",") else ","
    sio = StringIO(text)
    reader = csv.DictReader(sio, delimiter=sep)

    out = []
    for row in reader:
        raw_date = (row.get("date") or row.get("Date") or row.get("txn_date") or "").strip()
        raw_amount = (row.get("amount") or row.get("Amount") or "").strip()
        if not raw_date or not raw_amount:
            continue

        # date parsing
        d: date
        try:
            if "-" in raw_date:
                d = datetime.strptime(raw_date, "%Y-%m-%d").date()
            else:
                d = datetime.strptime(raw_date, "%d/%m/%Y").date()
        except Exception:
            continue

        # amount parsing
        raw_amount = raw_amount.replace(" ", "").replace(",", ".")
        try:
            amt = Decimal(raw_amount)
        except Exception:
            continue

        out.append(
            {
                "txn_date": d,
                "amount": amt,
                "description": (row.get("description") or row.get("Description") or "").strip() or None,
                "category": (row.get("category") or row.get("Category") or "").strip() or None,
                "counterparty": (row.get("counterparty") or row.get("Counterparty") or "").strip() or None,
                "reference": (row.get("reference") or row.get("Reference") or "").strip() or None,
            }
        )

    return out


def parse_transactions_csv_mapped(
    text: str,
    mapping: dict,
    *,
    delimiter: str = "auto",
    date_format: str = "auto",
) -> list[dict]:
    """Parse CSV using an explicit column mapping.

    mapping keys accepted:
      - date (required)
      - amount (required)
      - description, category, counterparty, reference (optional)
    """
    if not text:
        return []

    date_col = (mapping.get("date") or "").strip()
    amount_col = (mapping.get("amount") or "").strip()
    if not date_col or not amount_col:
        return []

    sample = text[:2048]
    if delimiter == "semicolon":
        sep = ";"
    elif delimiter == "tab":
        sep = "\t"
    elif delimiter == "comma":
        sep = ","
    else:
        sep = ";" if sample.count(";") > sample.count(",") else ","

    if date_format == "ymd":
        date_formats = ["%Y-%m-%d", "%Y/%m/%d"]
    elif date_format == "dmy":
        date_formats = ["%d/%m/%Y", "%d-%m-%Y"]
    elif date_format == "mdy":
        date_formats = ["%m/%d/%Y", "%m-%d-%Y"]
    else:
        date_formats = ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y"]

    sio = StringIO(text)
    reader = csv.DictReader(sio, delimiter=sep)

    out = []
    for row in reader:
        raw_date = (row.get(date_col) or "").strip()
        raw_amount = (row.get(amount_col) or "").strip()
        if not raw_date or not raw_amount:
            continue

        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(raw_date, fmt).date()
                break
            except Exception:
                continue
        if parsed_date is None:
            continue

        amount_norm = raw_amount.replace("\u00a0", " ").replace(" ", "")
        if amount_norm.count(",") > 0 and amount_norm.count(".") > 0:
            if amount_norm.rfind(",") > amount_norm.rfind("."):
                amount_norm = amount_norm.replace(".", "").replace(",", ".")
            else:
                amount_norm = amount_norm.replace(",", "")
        else:
            amount_norm = amount_norm.replace(",", ".")

        try:
            amount = Decimal(amount_norm)
        except Exception:
            continue

        desc_col = (mapping.get("description") or "").strip()
        cat_col = (mapping.get("category") or "").strip()
        cp_col = (mapping.get("counterparty") or "").strip()
        ref_col = (mapping.get("reference") or "").strip()

        out.append(
            {
                "txn_date": parsed_date,
                "amount": amount,
                "description": (row.get(desc_col) or "").strip() or None,
                "category": (row.get(cat_col) or "").strip() or None,
                "counterparty": (row.get(cp_col) or "").strip() or None,
                "reference": (row.get(ref_col) or "").strip() or None,
            }
        )

    return out

# -----------------
# Bank statement import (PDF)
# -----------------

import re
from io import BytesIO
from typing import Optional


def _parse_money(raw: str) -> Optional[Decimal]:
    """Parse money strings like '1 234,56', '1234.56', '-12.34'."""
    s = (raw or '').strip()
    if not s:
        return None
    # remove currency symbols and spaces
    s = re.sub(r"[€$£]", "", s)
    s = s.replace("\u00a0", " ").replace(" ", "")
    # handle thousand separators
    # if both ',' and '.', assume one is thousands
    if s.count(",") > 0 and s.count(".") > 0:
        # assume last separator is decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return None


_DATE_RE = re.compile(r"^(?P<d>\d{2}[\/\-]\d{2}[\/\-]\d{4}|\d{4}[\/\-]\d{2}[\/\-]\d{2})")


def parse_bank_statement_pdf_local(pdf_bytes: bytes) -> list[dict]:
    """Best-effort PDF statement parser.

    This is heuristic-based and designed for *common* bank statement layouts:
    lines that start with a date and contain a debit/credit amount.

    Output rows follow the same shape as parse_transactions_csv().
    """
    if not pdf_bytes:
        return []

    try:
        import pdfplumber  # type: ignore
    except Exception:
        # Dependency missing; return empty so UI can show an actionable message.
        return []

    text_lines: list[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ''
            for ln in t.splitlines():
                ln = (ln or '').strip()
                if ln:
                    text_lines.append(ln)

    out: list[dict] = []

    # Common patterns:
    #  - DATE  DESCRIPTION  -12,34
    #  - DATE  DESCRIPTION  12,34
    #  - DATE  DESCRIPTION  12,34  0,00
    #  - DATE  DESCRIPTION  0,00  12,34
    money_re = re.compile(r"[-+]?\d[\d\s.,]*\d")

    for ln in text_lines:
        m = _DATE_RE.match(ln)
        if not m:
            continue
        raw_date = m.group('d')
        rest = ln[len(raw_date):].strip()

        # Collect money candidates
        nums = [x.group(0) for x in money_re.finditer(rest)]
        money = [_parse_money(n) for n in nums]
        money = [x for x in money if x is not None]
        if not money:
            continue

        # Choose amount:
        # If 2 amounts, treat as (debit, credit) and use non-zero.
        amount: Optional[Decimal] = None
        if len(money) >= 2:
            debit = money[-2]
            credit = money[-1]
            if credit != 0 and debit == 0:
                amount = credit
            elif debit != 0 and credit == 0:
                amount = -abs(debit)
            else:
                # fallback: take last, use sign if present in text
                amount = credit
        else:
            # one amount: keep sign if present, otherwise infer from keywords
            amount = money[-1]
            if '-' in nums[-1]:
                amount = -abs(amount)

        # Description: remove trailing numbers
        desc = re.sub(r"\s+[-+]?\d[\d\s.,]*\d.*$", "", rest).strip() or None

        # date parsing
        try:
            if raw_date.startswith(tuple('0123456789')) and raw_date[:4].isdigit() and raw_date[4] in "-/":
                d = datetime.strptime(raw_date.replace('-', '/'), "%Y/%m/%d").date()
            else:
                d = datetime.strptime(raw_date.replace('-', '/'), "%d/%m/%Y").date()
        except Exception:
            continue

        out.append(
            {
                "txn_date": d,
                "amount": amount,
                "description": desc,
                "category": None,
                "counterparty": None,
                "reference": None,
            }
        )

    # De-duplicate exact duplicates from parsing noise
    uniq = []
    seen = set()
    for r in out:
        sig = (r['txn_date'], str(r['amount']), (r.get('description') or '').strip())
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append(r)
    return uniq


def parse_bank_statement_pdf_via_api(
    pdf_bytes: bytes,
    filename: str,
    endpoint: str,
    api_key: str | None = None,
    timeout_s: int = 60,
) -> list[dict]:
    """Send the PDF to an external parsing API.

    Expected response JSON (example):
      {"transactions": [{"date":"2026-01-31","amount":-12.34,"description":"...","counterparty":"...","reference":"..."}, ...]}

    If the response doesn't match, returns an empty list.
    """
    if not pdf_bytes or not endpoint:
        return []

    try:
        import requests  # type: ignore
    except Exception:
        return []

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    files = {"file": (filename or "statement.pdf", pdf_bytes, "application/pdf")}

    try:
        r = requests.post(endpoint, files=files, headers=headers, timeout=timeout_s)
        r.raise_for_status()
        data = r.json() if r.content else {}
    except Exception:
        return []

    txns = data.get("transactions") if isinstance(data, dict) else None
    if not isinstance(txns, list):
        return []

    out: list[dict] = []
    for t in txns:
        if not isinstance(t, dict):
            continue
        raw_date = (t.get("date") or "").strip()
        raw_amount = t.get("amount")
        if not raw_date:
            continue
        try:
            d = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except Exception:
            # allow DD/MM/YYYY
            try:
                d = datetime.strptime(raw_date, "%d/%m/%Y").date()
            except Exception:
                continue
        try:
            amt = Decimal(str(raw_amount))
        except Exception:
            continue
        out.append(
            {
                "txn_date": d,
                "amount": amt,
                "description": (t.get("description") or "").strip() or None,
                "category": (t.get("category") or "").strip() or None,
                "counterparty": (t.get("counterparty") or "").strip() or None,
                "reference": (t.get("reference") or "").strip() or None,
            }
        )

    return out
