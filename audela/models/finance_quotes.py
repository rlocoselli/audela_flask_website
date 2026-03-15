from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import UniqueConstraint

from ..extensions import db


class FinanceQuote(db.Model):
    """Commercial quote (devis) that can be signed and converted to invoice."""

    __tablename__ = "finance_quotes"
    __table_args__ = (
        db.Index("ix_fin_quote_tenant_company_date", "tenant_id", "company_id", "issue_date"),
        UniqueConstraint("tenant_id", "company_id", "quote_number", name="uq_fin_quote_number"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    quote_number = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft")  # draft|sent|signed|converted|cancelled

    issue_date = db.Column(db.Date, nullable=False, default=date.today)
    valid_until = db.Column(db.Date, nullable=True)

    currency = db.Column(db.String(8), db.ForeignKey("finance_currencies.code"), nullable=False, default="EUR")
    counterparty_id = db.Column(db.Integer, db.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True, index=True)

    fiscal_country = db.Column(db.String(8), nullable=False, default="EU")  # EU|BR
    notes = db.Column(db.Text, nullable=True)

    total_net = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    total_tax = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    total_gross = db.Column(db.Numeric(18, 2), nullable=False, default=0)

    signer_name = db.Column(db.String(160), nullable=True)
    signature_data_url = db.Column(db.Text, nullable=True)
    signed_at = db.Column(db.DateTime, nullable=True)
    signed_ip = db.Column(db.String(64), nullable=True)
    signed_user_agent = db.Column(db.String(255), nullable=True)

    converted_invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("finance_invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship("FinanceCompany")
    counterparty = db.relationship("FinanceCounterparty")
    currency_ref = db.relationship("FinanceCurrency", foreign_keys=[currency])
    converted_invoice = db.relationship("FinanceInvoice", foreign_keys=[converted_invoice_id])

    lines = db.relationship("FinanceQuoteLine", back_populates="quote", cascade="all, delete-orphan")


class FinanceQuoteLine(db.Model):
    __tablename__ = "finance_quote_lines"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    quote_id = db.Column(db.Integer, db.ForeignKey("finance_quotes.id", ondelete="CASCADE"), nullable=False, index=True)

    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    vat_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0)

    # Brazil fiscal fields
    icms_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0)
    ipi_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0)
    pis_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0)
    cofins_rate = db.Column(db.Numeric(9, 4), nullable=False, default=0)

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

    quote = db.relationship("FinanceQuote", back_populates="lines")
