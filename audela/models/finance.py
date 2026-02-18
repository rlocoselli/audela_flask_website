from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import UniqueConstraint

from ..extensions import db


class FinanceCompany(db.Model):
    """Company/SME entity within a tenant (multi-company)."""

    __tablename__ = "finance_companies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_fin_company_slug_per_tenant"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    slug = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(160), nullable=False)

    base_currency = db.Column(db.String(8), db.ForeignKey("finance_currencies.code"), nullable=False, default="EUR")
    country = db.Column(db.String(80), nullable=True)

    # Legal / invoicing fields (optional)
    country_code = db.Column(db.String(2), nullable=True, doc="ISO 3166-1 alpha-2")
    vat_number = db.Column(db.String(64), nullable=True)
    siret = db.Column(db.String(32), nullable=True)
    registration_number = db.Column(db.String(64), nullable=True, doc="e.g., RCS / REA / other")

    address_line1 = db.Column(db.String(160), nullable=True)
    address_line2 = db.Column(db.String(160), nullable=True)
    postal_code = db.Column(db.String(32), nullable=True)
    city = db.Column(db.String(80), nullable=True)
    state = db.Column(db.String(80), nullable=True)

    email = db.Column(db.String(160), nullable=True)
    phone = db.Column(db.String(80), nullable=True)

    iban = db.Column(db.String(64), nullable=True)
    bic = db.Column(db.String(32), nullable=True)

    base_currency_ref = db.relationship('FinanceCurrency', foreign_keys=[base_currency])

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship("Tenant", backref=db.backref("finance_companies", lazy="dynamic"))


class FinanceAccount(db.Model):
    """A balance sheet account used for cashflow, NII and risk computations."""

    __tablename__ = "finance_accounts"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name = db.Column(db.String(160), nullable=False)
    account_type = db.Column(
        db.String(32),
        nullable=False,
        default="bank",
        doc="cash|bank|loan|deposit|receivable|payable|credit_line|other",
    )
    side = db.Column(db.String(16), nullable=False, default="asset", doc="asset|liability")
    currency = db.Column(db.String(8), db.ForeignKey("finance_currencies.code"), nullable=False, default="EUR")

    # Balances and limits
    currency_ref = db.relationship('FinanceCurrency', foreign_keys=[currency])

    # Balances and limits (stored as Numeric for safer rounding)
    balance = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    limit_amount = db.Column(db.Numeric(18, 2), nullable=True)  # for credit lines

    # Interest parameters (optional)
    is_interest_bearing = db.Column(db.Boolean, nullable=False, default=False)
    annual_rate = db.Column(db.Numeric(9, 6), nullable=True)  # 0.05 => 5%
    rate_type = db.Column(db.String(16), nullable=False, default="fixed")  # fixed|float
    repricing_date = db.Column(db.Date, nullable=True)
    maturity_date = db.Column(db.Date, nullable=True)

    counterparty_id = db.Column(db.Integer, db.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True)

    # Legacy/free-text counterparty (kept for imports & backward compatibility)
    counterparty = db.Column(db.String(160), nullable=True)  # bank / lender / customer etc

    counterparty_ref = db.relationship("FinanceCounterparty")

    # Bank identification (IBAN/BIC for this specific account, not company-level)
    iban = db.Column(db.String(64), nullable=True)
    bic = db.Column(db.String(32), nullable=True)

    # Optional accounting mapping (used for reconciliation)
    gl_account_id = db.Column(db.Integer, db.ForeignKey("finance_gl_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship("FinanceCompany", backref=db.backref("accounts", lazy="dynamic"))


class FinanceTransaction(db.Model):
    """A transaction line linked to an account (historical or future-dated forecast)."""

    __tablename__ = "finance_transactions"
    __table_args__ = (
        db.Index("ix_fin_txn_tenant_company_date", "tenant_id", "company_id", "txn_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id = db.Column(
        db.Integer, db.ForeignKey("finance_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    txn_date = db.Column(db.Date, nullable=False, default=date.today)
    # Convention: amount > 0 is inflow, amount < 0 is outflow
    amount = db.Column(db.Numeric(18, 2), nullable=False)

    description = db.Column(db.String(255), nullable=True)
    # New directory-based category (preferred). Keep legacy free-text for backward compatibility.
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("finance_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category = db.Column(db.String(64), nullable=True)  # legacy/free-text
    counterparty_id = db.Column(db.Integer, db.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True)
    counterparty = db.Column(db.String(160), nullable=True)  # legacy/free-text

    # Reconciliation
    ledger_voucher_id = db.Column(db.Integer, db.ForeignKey("finance_ledger_vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    reconciled_at = db.Column(db.DateTime, nullable=True)

    # Optional accounting mapping (used for reconciliation / ledger exports)
    gl_account_id = db.Column(
        db.Integer,
        db.ForeignKey("finance_gl_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    counterparty_ref = db.relationship("FinanceCounterparty")
    category_ref = db.relationship("FinanceCategory", foreign_keys=[category_id])
    gl_account_ref = db.relationship("FinanceGLAccount", foreign_keys=[gl_account_id])
    reference = db.Column(db.String(120), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    company = db.relationship("FinanceCompany", backref=db.backref("transactions", lazy="dynamic"))
    account = db.relationship("FinanceAccount", backref=db.backref("transactions", lazy="dynamic"))


class FinanceReportSnapshot(db.Model):
    """Optional stored results for audits / history (JSON payload)."""

    __tablename__ = "finance_report_snapshots"
    __table_args__ = (
        db.Index(
            "ix_fin_snap_tenant_company_type_date",
            "tenant_id",
            "company_id",
            "report_type",
            "as_of",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    report_type = db.Column(db.String(32), nullable=False)  # cashflow|nii|gaps|liquidity|risk
    as_of = db.Column(db.Date, nullable=False, default=date.today)

    payload_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    company = db.relationship("FinanceCompany", backref=db.backref("report_snapshots", lazy="dynamic"))
