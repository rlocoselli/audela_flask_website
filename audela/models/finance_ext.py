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
    parent_id = db.Column(db.Integer, db.ForeignKey("finance_gl_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0, index=True)

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


class FinanceInvestment(db.Model):
    """Investment registry (EDF products, stock exchange positions).

    MVP: stores current valuation and links to settlement account for cash impact.
    """

    __tablename__ = "finance_investments"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey("finance_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.String(160), nullable=False)
    provider = db.Column(db.String(32), nullable=False, default="stock_exchange")  # edf|stock_exchange
    instrument_code = db.Column(db.String(64), nullable=True)

    account_id = db.Column(db.Integer, db.ForeignKey("finance_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    currency_code = db.Column(db.String(8), db.ForeignKey("finance_currencies.code"), nullable=True)

    invested_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    current_value = db.Column(db.Numeric(18, 2), nullable=True)

    started_on = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(24), nullable=False, default="active")  # active|closed
    notes = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("FinanceAccount")
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


class FinanceProduct(db.Model):
    """Product registry with automatic VAT application based on product nature.
    
    Used for invoicing, automatic tax calculations, and transaction categorization.
    """

    __tablename__ = "finance_products"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    code = db.Column(db.String(32), nullable=True, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(500), nullable=True)

    # Product classification
    product_type = db.Column(db.String(24), nullable=False, default="service")  # good|service|digital|other
    category_id = db.Column(db.Integer, db.ForeignKey("finance_categories.id", ondelete="SET NULL"), nullable=True, index=True)

    # Pricing
    unit_price = db.Column(db.Numeric(18, 4), nullable=False)
    currency_code = db.Column(db.String(8), db.ForeignKey("finance_currencies.code"), nullable=False, default="EUR")

    # VAT / Tax configuration
    vat_rate = db.Column(db.Numeric(9, 4), nullable=False, default=20)  # percent (e.g., 20.00 for 20%)
    vat_applies = db.Column(db.Boolean, nullable=False, default=True)  # whether VAT is automatically applied
    vat_reverse_charge = db.Column(db.Boolean, nullable=False, default=False)  # for reverse charge scenarios
    tax_exempt_reason = db.Column(db.String(255), nullable=True)  # e.g., "export", "intra-EU", etc.

    # Optional GL account mapping
    gl_account_id = db.Column(db.Integer, db.ForeignKey("finance_gl_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    vat_gl_account_id = db.Column(db.Integer, db.ForeignKey("finance_gl_accounts.id", ondelete="SET NULL"), nullable=True)

    status = db.Column(db.String(32), nullable=False, default="active")  # active|inactive|archived
    notes = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category_ref = relationship("FinanceCategory", foreign_keys=[category_id])
    gl_account = relationship("FinanceGLAccount", foreign_keys=[gl_account_id])
    vat_gl_account = relationship("FinanceGLAccount", foreign_keys=[vat_gl_account_id])
    currency = relationship("FinanceCurrency")


class FinanceDailyBalance(db.Model):
    """Daily balance snapshot for each account.
    
    Used for historical balance tracking, trend analysis, and daily reconciliation.
    """

    __tablename__ = "finance_daily_balances"
    __table_args__ = (
        db.Index("ix_fin_daily_balance_account_date", "account_id", "balance_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("finance_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    balance_date = db.Column(db.Date, nullable=False, index=True)
    opening_balance = db.Column(db.Numeric(18, 2), nullable=False)
    closing_balance = db.Column(db.Numeric(18, 2), nullable=False)
    
    # Intra-day tracking
    daily_inflow = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    daily_outflow = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    transaction_count = db.Column(db.Integer, nullable=False, default=0)

    # Reconciliation status
    is_reconciled = db.Column(db.Boolean, nullable=False, default=False)
    reconciled_at = db.Column(db.DateTime, nullable=True)

    # Notes for manual reconciliation
    reconciliation_notes = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("FinanceAccount", backref=db.backref("daily_balances", lazy="dynamic"))


class FinanceAdjustment(db.Model):
    """Account adjustments (e.g., bank fees, interest, corrections).
    
    Tracks all adjustments with full audit trail through adjustment logs.
    """

    __tablename__ = "finance_adjustments"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("finance_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    adjustment_date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Numeric(18, 2), nullable=False)  # can be positive or negative
    
    # Classification
    reason = db.Column(db.String(64), nullable=False)  # interest|fee|correction|rounding|other
    description = db.Column(db.String(300), nullable=True)

    # Reference to related GL account for accounting purposes
    gl_account_id = db.Column(db.Integer, db.ForeignKey("finance_gl_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("finance_categories.id", ondelete="SET NULL"), nullable=True, index=True)

    # Optional counterparty (e.g., bank charges from a specific bank)
    counterparty_id = db.Column(db.Integer, db.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True, index=True)

    # Status tracking
    status = db.Column(db.String(32), nullable=False, default="pending")  # pending|approved|rejected|voided
    approved_by_user_id = db.Column(db.Integer, nullable=True)  # user who approved
    approved_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("FinanceAccount", backref=db.backref("adjustments", lazy="dynamic"))
    gl_account = relationship("FinanceGLAccount", foreign_keys=[gl_account_id])
    category = relationship("FinanceCategory", foreign_keys=[category_id])
    counterparty = relationship("FinanceCounterparty", foreign_keys=[counterparty_id])
    logs = relationship("FinanceAdjustmentLog", back_populates="adjustment", cascade="all, delete-orphan")


class FinanceAdjustmentLog(db.Model):
    """Audit trail for adjustments (status changes, approvals, etc.).
    
    Maintains complete history of who did what and when.
    """

    __tablename__ = "finance_adjustment_logs"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    adjustment_id = db.Column(db.Integer, db.ForeignKey("finance_adjustments.id", ondelete="CASCADE"), nullable=False, index=True)

    user_id = db.Column(db.Integer, nullable=False)  # user who performed the action
    action = db.Column(db.String(32), nullable=False)  # created|modified|approved|rejected|voided
    
    # What changed
    previous_values = db.Column(db.JSON, nullable=True)  # dict of changed fields before
    new_values = db.Column(db.JSON, nullable=True)  # dict of changed fields after
    
    # Context
    change_reason = db.Column(db.String(300), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    adjustment = relationship("FinanceAdjustment", back_populates="logs")


class FinanceCounterpartyAttribute(db.Model):
    """Flexible attributes for counterparties (optional custom fields).
    
    Allows storing additional metadata per counterparty without schema modifications.
    Examples: payment_terms, credit_limit, contact_person, etc.
    """

    __tablename__ = "finance_counterparty_attributes"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    counterparty_id = db.Column(db.Integer, db.ForeignKey("finance_counterparties.id", ondelete="CASCADE"), nullable=False, index=True)

    attribute_name = db.Column(db.String(64), nullable=False)  # e.g., "payment_terms", "credit_limit"
    attribute_value = db.Column(db.String(500), nullable=False)  # stored as string, parsed as needed
    attribute_type = db.Column(db.String(32), nullable=False, default="string")  # string|number|date|boolean|json
    
    is_custom = db.Column(db.Boolean, nullable=False, default=True)  # distinguish custom vs system attrs

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    counterparty = relationship("FinanceCounterparty", backref=db.backref("attributes", lazy="dynamic"))


class FinancePowensConnection(db.Model):
    """Powens bank integration connection.
    
    Stores connection credentials and settings for Powens bank feed integration.
    Transactions are automatically imported and reconciled.
    """

    __tablename__ = "finance_powens_connections"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("finance_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Powens API credentials (encrypted in practice)
    powens_access_token = db.Column(db.LargeBinary, nullable=True)  # encrypted
    powens_secret_id = db.Column(db.String(120), nullable=True)
    institution_id = db.Column(db.String(120), nullable=True)  # Powens institution identifier
    
    # Account linking info
    powens_account_id = db.Column(db.String(120), nullable=True)  # provider account ID
    powens_account_name = db.Column(db.String(200), nullable=True)
    iban = db.Column(db.String(64), nullable=True)
    
    # Sync settings
    sync_enabled = db.Column(db.Boolean, nullable=False, default=True)
    last_sync_date = db.Column(db.DateTime, nullable=True)
    last_sync_status = db.Column(db.String(32), nullable=True)  # success|failure|pending
    sync_days_back = db.Column(db.Integer, nullable=False, default=90)  # sync last N days

    # Auto-import settings
    auto_import_enabled = db.Column(db.Boolean, nullable=False, default=True)
    auto_create_counterparty = db.Column(db.Boolean, nullable=False, default=True)
    auto_categorize = db.Column(db.Boolean, nullable=False, default=True)

    # Status
    status = db.Column(db.String(32), nullable=False, default="active")  # active|inactive|disconnected|error
    status_reason = db.Column(db.String(300), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("FinanceAccount")
    syncs = relationship("FinancePowensSyncLog", back_populates="connection", cascade="all, delete-orphan")


class FinancePowensSyncLog(db.Model):
    """Sync history log for Powens connections.
    
    Tracks each sync attempt with status, transactions imported, and any errors.
    """

    __tablename__ = "finance_powens_sync_logs"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    connection_id = db.Column(db.Integer, db.ForeignKey("finance_powens_connections.id", ondelete="CASCADE"), nullable=False, index=True)

    sync_start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sync_end_date = db.Column(db.DateTime, nullable=True)
    
    # Results
    transactions_imported = db.Column(db.Integer, nullable=False, default=0)
    transactions_skipped = db.Column(db.Integer, nullable=False, default=0)
    transactions_failed = db.Column(db.Integer, nullable=False, default=0)

    status = db.Column(db.String(32), nullable=False, default="pending")  # pending|success|partial|failure
    error_message = db.Column(db.String(500), nullable=True)
    
    # Metadata
    sync_metadata = db.Column(db.JSON, nullable=True)  # Powens response details

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    connection = relationship("FinancePowensConnection", back_populates="syncs")

