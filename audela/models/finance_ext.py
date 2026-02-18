from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import relationship

from ..extensions import db


class FinanceCategory(db.Model):
    __tablename__ = "finance_categories"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    code = db.Column(db.String(32), nullable=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(24), nullable=False, default="expense")  # income|expense|transfer|other

    default_gl_account_id = db.Column(db.Integer, db.ForeignKey("finance_gl_accounts.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    rules = relationship("FinanceCategoryRule", back_populates="category", cascade="all, delete-orphan")
    default_gl_account = relationship("FinanceGLAccount", foreign_keys=[default_gl_account_id])


class FinanceCategoryRule(db.Model):
    __tablename__ = "finance_category_rules"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    category_id = db.Column(db.Integer, db.ForeignKey("finance_categories.id", ondelete="CASCADE"), nullable=False, index=True)

    # Rule matching
    direction = db.Column(db.String(16), nullable=False, default="any")  # any | inflow | outflow
    keywords = db.Column(db.String(400), nullable=True)  # comma-separated keywords
    counterparty_id = db.Column(db.Integer, db.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True, index=True)
    min_amount = db.Column(db.Numeric(18, 2), nullable=True)
    max_amount = db.Column(db.Numeric(18, 2), nullable=True)
    priority = db.Column(db.Integer, nullable=False, default=100)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    category = relationship("FinanceCategory", back_populates="rules")


class FinanceBankConnection(db.Model):
    __tablename__ = "finance_bank_connections"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    provider = db.Column(db.String(32), nullable=False)  # bridge | revolut | manual
    label = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="active")

    # Bridge-specific linkage (kept as plain columns for easier ops)
    external_user_id = db.Column(db.String(120), nullable=True)
    item_id = db.Column(db.String(120), nullable=True)

    # Encrypted JSON: tokens, provider-specific metadata
    config_encrypted = db.Column(db.LargeBinary, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    accounts = relationship("FinanceBankAccountLink", back_populates="connection", cascade="all, delete-orphan")


class FinanceBankAccountLink(db.Model):
    __tablename__ = "finance_bank_account_links"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    connection_id = db.Column(db.Integer, db.ForeignKey("finance_bank_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_account_id = db.Column(db.String(120), nullable=False, index=True)
    provider_account_name = db.Column(db.String(200), nullable=True)
    currency_code = db.Column(db.String(8), nullable=True)

    finance_account_id = db.Column(db.Integer, db.ForeignKey("finance_accounts.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    connection = relationship("FinanceBankConnection", back_populates="accounts")
    finance_account = relationship("FinanceAccount")


class FinanceGLAccount(db.Model):
    __tablename__ = "finance_gl_accounts"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    code = db.Column(db.String(32), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(24), nullable=False, default="expense")  # asset|liability|equity|income|expense

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class FinanceLedgerVoucher(db.Model):
    __tablename__ = "finance_ledger_vouchers"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    voucher_date = db.Column(db.Date, nullable=False)
    reference = db.Column(db.String(120), nullable=True)
    description = db.Column(db.String(300), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    lines = relationship("FinanceLedgerLine", back_populates="voucher", cascade="all, delete-orphan")


class FinanceLedgerLine(db.Model):
    __tablename__ = "finance_ledger_lines"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    voucher_id = db.Column(db.Integer, db.ForeignKey("finance_ledger_vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    gl_account_id = db.Column(db.Integer, db.ForeignKey("finance_gl_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    txn_id = db.Column(db.Integer, db.ForeignKey("finance_transactions.id", ondelete="SET NULL"), nullable=True, index=True)

    counterparty_id = db.Column(db.Integer, db.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True, index=True)

    debit = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    credit = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    description = db.Column(db.String(300), nullable=True)

    voucher = relationship("FinanceLedgerVoucher", back_populates="lines")
    gl_account = relationship("FinanceGLAccount")


class FinanceLiability(db.Model):
    """Financing / liabilities registry (loans, debts, leases).

    MVP model used for reporting and cash planning.
    """

    __tablename__ = "finance_liabilities"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey("finance_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.String(160), nullable=False)
    lender_counterparty_id = db.Column(
        db.Integer,
        db.ForeignKey("finance_counterparties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    currency_code = db.Column(db.String(8), db.ForeignKey("finance_currencies.code"), nullable=True)

    principal_amount = db.Column(db.Numeric(18, 2), nullable=True)
    outstanding_amount = db.Column(db.Numeric(18, 2), nullable=True)
    interest_rate = db.Column(db.Numeric(9, 4), nullable=True)  # percent (e.g., 3.25)

    start_date = db.Column(db.Date, nullable=True)
    maturity_date = db.Column(db.Date, nullable=True)
    payment_frequency = db.Column(db.String(24), nullable=False, default="monthly")  # monthly|quarterly|yearly|other

    # Cash planning helpers (optional)
    installment_amount = db.Column(db.Numeric(18, 2), nullable=True)
    next_payment_date = db.Column(db.Date, nullable=True)

    notes = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    lender = relationship("FinanceCounterparty")
    currency = relationship("FinanceCurrency")


class FinanceRecurringTransaction(db.Model):
    """Recurring transactions template (e.g. rent, subscriptions).

    Generation is triggered manually in the MVP.
    """

    __tablename__ = "finance_recurring_transactions"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey("finance_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.String(160), nullable=False)

    account_id = db.Column(db.Integer, db.ForeignKey("finance_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = db.Column(db.String(16), nullable=False, default="outflow")  # inflow|outflow
    amount = db.Column(db.Numeric(18, 2), nullable=False)  # stored as positive; sign applied on generation
    currency_code = db.Column(db.String(8), db.ForeignKey("finance_currencies.code"), nullable=True)

    category_id = db.Column(db.Integer, db.ForeignKey("finance_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    counterparty_id = db.Column(db.Integer, db.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True, index=True)
    description = db.Column(db.String(255), nullable=True)

    frequency = db.Column(db.String(24), nullable=False, default="monthly")  # daily|weekly|monthly|yearly
    next_run_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("FinanceAccount")
    category_ref = relationship("FinanceCategory", foreign_keys=[category_id])
    counterparty_ref = relationship("FinanceCounterparty")
    currency = relationship("FinanceCurrency")

