from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, List, Dict, Tuple

from ..models.finance import FinanceTransaction, FinanceAccount
from ..models.finance_ext import FinanceRecurringTransaction, FinanceLiability
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


def compute_starting_cash(accounts: Iterable[FinanceAccount]) -> Decimal:
    total = Decimal("0")
    for a in accounts:
        if (a.account_type or "").lower() in {"cash", "bank"}:
            total += _d(a.balance)
    return total


def _period_key(granularity: str, d: date) -> date:
    g = (granularity or "daily").lower()
    if g == "weekly":
        # Monday as week start
        return d - timedelta(days=d.weekday())
    if g == "monthly":
        return date(d.year, d.month, 1)
    return d


def _next_date(freq: str, d: date) -> date:
    f = (freq or "monthly").lower()
    if f == "daily":
        return d + timedelta(days=1)
    if f == "weekly":
        return d + timedelta(days=7)
    if f == "yearly":
        return date(d.year + 1, d.month, d.day)
    # monthly (simple): add 1 month keeping day, clamp
    y = d.year + (1 if d.month == 12 else 0)
    m = 1 if d.month == 12 else d.month + 1
    # clamp day to last day of month
    import calendar

    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


@dataclass
class ProjectionPoint:
    period: date
    inflow: Decimal
    outflow: Decimal
    net: Decimal
    balance: Decimal


def project_cash_balance(
    *,
    start: date,
    end: date,
    granularity: str,
    starting_balance: Decimal,
    transactions: Iterable[FinanceTransaction],
    recurring: Iterable[FinanceRecurringTransaction],
    liabilities: Iterable[FinanceLiability],
    invoices: Iterable[FinanceInvoice],
) -> List[ProjectionPoint]:
    """Project cash balance using:
    - existing transactions (incl. future-dated)
    - recurring templates (not persisted)
    - liabilities installment schedule (if installment_amount + next_payment_date)
    - unpaid invoices (sale inflow, purchase outflow) on due_date (or issue_date)

    Currency: simplified (assumes single currency).
    """

    by_period: Dict[date, Tuple[Decimal, Decimal]] = {}

    def add(d: date, amt: Decimal):
        if d < start or d > end:
            return
        p = _period_key(granularity, d)
        inflow, outflow = by_period.get(p, (Decimal("0"), Decimal("0")))
        if amt >= 0:
            inflow += amt
        else:
            outflow += (-amt)
        by_period[p] = (inflow, outflow)

    # Existing transactions
    for t in transactions:
        add(t.txn_date, _d(t.amount))

    # Recurring templates
    for r in recurring:
        if not r.active:
            continue
        d = r.next_run_date
        while d <= end and (r.end_date is None or d <= r.end_date):
            amt = _d(r.amount)
            if (r.direction or "outflow").lower() == "outflow":
                amt = -abs(amt)
            else:
                amt = abs(amt)
            add(d, amt)
            d = _next_date(r.frequency, d)

    # Liabilities (installments)
    for l in liabilities:
        if l.installment_amount is None or l.next_payment_date is None:
            continue
        d = l.next_payment_date
        while d <= end:
            add(d, -abs(_d(l.installment_amount)))
            d = _next_date(l.payment_frequency, d)

    # Unpaid invoices
    for inv in invoices:
        if (inv.status or "draft").lower() in {"paid", "void"}:
            continue
        d = inv.due_date or inv.issue_date
        amt = _d(inv.total_gross)
        if (inv.invoice_type or "sale").lower() == "sale":
            add(d, abs(amt))
        else:
            add(d, -abs(amt))

    # Build ordered points
    periods = sorted(by_period.keys())
    # Ensure we have a starting point even if no cash events
    if not periods:
        periods = [_period_key(granularity, start)]
    # Ensure first period covers start
    first = _period_key(granularity, start)
    if periods[0] != first:
        periods.insert(0, first)

    bal = _d(starting_balance)
    out: List[ProjectionPoint] = []
    for p in periods:
        inflow, outflow = by_period.get(p, (Decimal("0"), Decimal("0")))
        net = inflow - outflow
        bal = bal + net
        out.append(ProjectionPoint(period=p, inflow=inflow, outflow=outflow, net=net, balance=bal))

    return out


def build_ui_alerts(series: List[ProjectionPoint], *, low_balance_threshold: Decimal) -> List[dict]:
    alerts: List[dict] = []
    if not series:
        return alerts

    min_pt = min(series, key=lambda p: p.balance)
    if min_pt.balance < 0:
        alerts.append({
            "level": "danger",
            "title": "Solde projeté négatif",
            "message": f"Le solde projeté devient négatif ({min_pt.balance:.2f}) à partir du {min_pt.period.isoformat()}.",
        })
    elif min_pt.balance < low_balance_threshold:
        alerts.append({
            "level": "warning",
            "title": "Solde projeté bas",
            "message": f"Le solde projeté descend sous le seuil ({low_balance_threshold:.2f}) le {min_pt.period.isoformat()} (solde {min_pt.balance:.2f}).",
        })

    return alerts
