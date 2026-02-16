from __future__ import annotations

from datetime import datetime

from ..extensions import db


class FinanceCurrency(db.Model):
    """Reference table for currencies.

    We keep it global (not tenant-scoped) so all tenants share the same ISO codes.
    Tenants can still choose which codes to use in their companies/accounts.
    """

    __tablename__ = "finance_currencies"

    code = db.Column(db.String(8), primary_key=True)  # e.g. EUR
    name = db.Column(db.String(80), nullable=True)  # e.g. Euro
    symbol = db.Column(db.String(12), nullable=True)  # e.g. €
    decimals = db.Column(db.Integer, nullable=False, default=2)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class FinanceCounterparty(db.Model):
    """Counterparty directory for a tenant (optionally scoped to a company).

    Examples:
    - a bank (BNP, Revolut)
    - a supplier/customer
    - tax authority

    For SMEs, this is used for risk / concentration and for transaction labeling.
    """

    __tablename__ = "finance_counterparties"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=True, index=True)

    name = db.Column(db.String(160), nullable=False)
    kind = db.Column(
        db.String(32),
        nullable=False,
        default="other",
        doc="bank|supplier|customer|employee|tax|other",
    )

    default_currency = db.Column(db.String(8), db.ForeignKey("finance_currencies.code"), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tenant = db.relationship("Tenant", backref=db.backref("finance_counterparties", lazy="dynamic"))
    company = db.relationship("FinanceCompany", backref=db.backref("counterparties", lazy="dynamic"))
    currency = db.relationship("FinanceCurrency")


class FinanceStatementImport(db.Model):
    """Tracks a statement (PDF/CSV) import and the parsing method used."""

    __tablename__ = "finance_statement_imports"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("finance_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    filename = db.Column(db.String(255), nullable=True)
    provider = db.Column(db.String(64), nullable=False, default="local")  # local|external

    imported_rows = db.Column(db.Integer, nullable=False, default=0)
    skipped_rows = db.Column(db.Integer, nullable=False, default=0)

    payload_json = db.Column(db.JSON, nullable=True)  # optional: provider response / metadata

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    company = db.relationship("FinanceCompany")
    account = db.relationship("FinanceAccount")
