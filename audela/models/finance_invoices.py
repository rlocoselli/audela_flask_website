from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import UniqueConstraint

from ..extensions import db


class FinanceSetting(db.Model):
    """Key/value settings for finance module.

    Used for things like alerts granularity (daily/weekly/monthly).
    """

    __tablename__ = "finance_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "company_id", "key", name="uq_fin_settings_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    key = db.Column(db.String(80), nullable=False)
    value_json = db.Column(db.JSON, nullable=False, default=dict)

    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class FinanceInvoice(db.Model):
    """Invoices used for e-invoicing exports and cash planning.

    - invoice_type: sale|purchase
    - status: draft|sent|paid|void
    """

    __tablename__ = "finance_invoices"
    __table_args__ = (
        db.Index("ix_fin_invoice_tenant_company_date", "tenant_id", "company_id", "issue_date"),
        UniqueConstraint("tenant_id", "company_id", "invoice_number", name="uq_fin_invoice_number"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    invoice_number = db.Column(db.String(64), nullable=False)
    invoice_type = db.Column(db.String(16), nullable=False, default="sale")  # sale|purchase
    status = db.Column(db.String(16), nullable=False, default="draft")  # draft|sent|paid|void

    issue_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=True)

    currency = db.Column(db.String(8), db.ForeignKey("finance_currencies.code"), nullable=False, default="EUR")

    counterparty_id = db.Column(db.Integer, db.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True, index=True)

    # Optional: account used when marking invoice as paid
    settlement_account_id = db.Column(db.Integer, db.ForeignKey("finance_accounts.id", ondelete="SET NULL"), nullable=True, index=True)

    notes = db.Column(db.Text, nullable=True)

    # Fiscal metadata (SEFAZ readiness for BR invoices)
    fiscal_country = db.Column(db.String(8), nullable=False, default="EU")  # EU|BR
    document_model = db.Column(db.String(8), nullable=False, default="55")
    document_series = db.Column(db.String(8), nullable=False, default="1")
    sefaz_environment = db.Column(db.String(16), nullable=False, default="homologation")  # homologation|production
    natureza_operacao = db.Column(db.String(120), nullable=True)
    operation_destination = db.Column(db.String(8), nullable=False, default="1")
    payment_indicator = db.Column(db.String(8), nullable=False, default="0")
    presence_indicator = db.Column(db.String(8), nullable=False, default="1")
    final_consumer = db.Column(db.Boolean, nullable=False, default=True)
    invoice_purpose = db.Column(db.String(8), nullable=False, default="1")
    emission_type = db.Column(db.String(8), nullable=False, default="1")
    cnf_code = db.Column(db.String(16), nullable=True)
    needs_sefaz_validation = db.Column(db.Boolean, nullable=False, default=False)

    total_net = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    total_tax = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    total_gross = db.Column(db.Numeric(18, 2), nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship("FinanceCompany")
    counterparty = db.relationship("FinanceCounterparty")
    currency_ref = db.relationship("FinanceCurrency", foreign_keys=[currency])
    settlement_account = db.relationship("FinanceAccount")

    lines = db.relationship("FinanceInvoiceLine", back_populates="invoice", cascade="all, delete-orphan")


class FinanceInvoiceLine(db.Model):
    __tablename__ = "finance_invoice_lines"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    invoice_id = db.Column(db.Integer, db.ForeignKey("finance_invoices.id", ondelete="CASCADE"), nullable=False, index=True)

    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    vat_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0, doc="Percent, e.g. 20.0")

    # Brazil fiscal fields (tax rates in percent)
    icms_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0)
    ipi_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0)
    pis_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0)
    cofins_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0)

    # SEFAZ/NFe product tax classification
    ncm_code = db.Column(db.String(16), nullable=True)
    cfop_code = db.Column(db.String(8), nullable=True)
    cest_code = db.Column(db.String(16), nullable=True)
    cst_icms = db.Column(db.String(4), nullable=True)
    cst_ipi = db.Column(db.String(4), nullable=True)
    cst_pis = db.Column(db.String(4), nullable=True)
    cst_cofins = db.Column(db.String(4), nullable=True)

    net_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    gross_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    icms_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    ipi_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    pis_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    cofins_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)

    invoice = db.relationship("FinanceInvoice", back_populates="lines")
