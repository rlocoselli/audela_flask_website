from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from typing import Iterable, Optional

from ..models.finance_ext import FinanceLedgerVoucher, FinanceLedgerLine


def export_fec_csv(
    *,
    vouchers: Iterable[FinanceLedgerVoucher],
    lines: Iterable[FinanceLedgerLine],
    as_of: Optional[date] = None,
) -> str:
    """Export a minimal French FEC-like CSV (pipe separated).

    Disclaimer: Real FEC exports depend on the accounting system setup (journals, numbering,
    auxiliary accounts, lettering, validation dates...). This export provides the required
    columns with best-effort data from the MVP ledger.
    """
    as_of = as_of or date.today()
    voucher_by_id = {v.id: v for v in vouchers}

    out = StringIO()
    writer = csv.writer(out, delimiter="|")
    writer.writerow(
        [
            "JournalCode",
            "JournalLib",
            "EcritureNum",
            "EcritureDate",
            "CompteNum",
            "CompteLib",
            "CompAuxNum",
            "CompAuxLib",
            "PieceRef",
            "PieceDate",
            "EcritureLib",
            "Debit",
            "Credit",
            "EcritureLet",
            "DateLet",
            "ValidDate",
            "MontantDevise",
            "Idevise",
        ]
    )

    for ln in lines:
        v = voucher_by_id.get(ln.voucher_id)
        if not v:
            continue
        dt = v.voucher_date
        writer.writerow(
            [
                "OD",  # JournalCode
                "Operations diverses",  # JournalLib
                str(v.id),
                dt.strftime("%Y%m%d"),
                (ln.gl_account.code if ln.gl_account else ""),
                (ln.gl_account.name if ln.gl_account else ""),
                "",  # CompAuxNum
                "",  # CompAuxLib
                v.reference or "",
                dt.strftime("%Y%m%d"),
                (ln.description or v.description or "")[:200],
                f"{float(ln.debit or 0):.2f}",
                f"{float(ln.credit or 0):.2f}",
                "",  # EcritureLet
                "",  # DateLet
                dt.strftime("%Y%m%d"),
                "",  # MontantDevise
                "",  # Idevise
            ]
        )

    return out.getvalue()


def export_it_ledger_csv(
    *,
    vouchers: Iterable[FinanceLedgerVoucher],
    lines: Iterable[FinanceLedgerLine],
) -> str:
    """Export a simple Italian-style ledger CSV.

    Not a substitute for an official Libro Giornale / registri IVA export,
    but a useful baseline export (date, doc ref, account, debit, credit).
    """
    voucher_by_id = {v.id: v for v in vouchers}
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(["Data", "Protocollo", "Descrizione", "Conto", "Dare", "Avere", "Riferimento"])
    for ln in lines:
        v = voucher_by_id.get(ln.voucher_id)
        if not v:
            continue
        writer.writerow(
            [
                v.voucher_date.isoformat(),
                v.reference or str(v.id),
                (ln.description or v.description or "")[:200],
                (ln.gl_account.code if ln.gl_account else ""),
                f"{float(ln.debit or 0):.2f}",
                f"{float(ln.credit or 0):.2f}",
                "AUDELA",
            ]
        )
    return out.getvalue()
