from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import UniqueConstraint

from ..extensions import db


class CreditCountry(db.Model):
    __tablename__ = "credit_countries"

    id = db.Column(db.Integer, primary_key=True)
    iso_code = db.Column(db.String(2), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    name_fr = db.Column(db.String(120), nullable=True)
    name_en = db.Column(db.String(120), nullable=True)
    name_pt = db.Column(db.String(120), nullable=True)
    name_es = db.Column(db.String(120), nullable=True)
    name_it = db.Column(db.String(120), nullable=True)
    name_de = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def display_name(self, lang: str | None = None) -> str:
        code = (lang or "").split("-")[0].lower()
        value = getattr(self, f"name_{code}", None)
        return value or self.name_fr or self.name_en or self.name


class CreditSector(db.Model):
    __tablename__ = "credit_sectors"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    name_fr = db.Column(db.String(120), nullable=True)
    name_en = db.Column(db.String(120), nullable=True)
    name_pt = db.Column(db.String(120), nullable=True)
    name_es = db.Column(db.String(120), nullable=True)
    name_it = db.Column(db.String(120), nullable=True)
    name_de = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def display_name(self, lang: str | None = None) -> str:
        code = (lang or "").split("-")[0].lower()
        value = getattr(self, f"name_{code}", None)
        return value or self.name_fr or self.name_en or self.name


class CreditRating(db.Model):
    __tablename__ = "credit_ratings"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), nullable=False, unique=True, index=True)
    label_fr = db.Column(db.String(120), nullable=True)
    label_en = db.Column(db.String(120), nullable=True)
    label_pt = db.Column(db.String(120), nullable=True)
    label_es = db.Column(db.String(120), nullable=True)
    label_it = db.Column(db.String(120), nullable=True)
    label_de = db.Column(db.String(120), nullable=True)
    rank_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def display_label(self, lang: str | None = None) -> str:
        code = (lang or "").split("-")[0].lower()
        value = getattr(self, f"label_{code}", None)
        return value or self.label_fr or self.label_en or self.code


class CreditFacilityType(db.Model):
    __tablename__ = "credit_facility_types"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    label = db.Column(db.String(120), nullable=False)
    label_fr = db.Column(db.String(120), nullable=True)
    label_en = db.Column(db.String(120), nullable=True)
    label_pt = db.Column(db.String(120), nullable=True)
    label_es = db.Column(db.String(120), nullable=True)
    label_it = db.Column(db.String(120), nullable=True)
    label_de = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def display_label(self, lang: str | None = None) -> str:
        code = (lang or "").split("-")[0].lower()
        value = getattr(self, f"label_{code}", None)
        return value or self.label_fr or self.label_en or self.label


class CreditCollateralType(db.Model):
    __tablename__ = "credit_collateral_types"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    label = db.Column(db.String(120), nullable=False)
    label_fr = db.Column(db.String(120), nullable=True)
    label_en = db.Column(db.String(120), nullable=True)
    label_pt = db.Column(db.String(120), nullable=True)
    label_es = db.Column(db.String(120), nullable=True)
    label_it = db.Column(db.String(120), nullable=True)
    label_de = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def display_label(self, lang: str | None = None) -> str:
        code = (lang or "").split("-")[0].lower()
        value = getattr(self, f"label_{code}", None)
        return value or self.label_fr or self.label_en or self.label


class CreditGuaranteeType(db.Model):
    __tablename__ = "credit_guarantee_types"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    label = db.Column(db.String(120), nullable=False)
    label_fr = db.Column(db.String(120), nullable=True)
    label_en = db.Column(db.String(120), nullable=True)
    label_pt = db.Column(db.String(120), nullable=True)
    label_es = db.Column(db.String(120), nullable=True)
    label_it = db.Column(db.String(120), nullable=True)
    label_de = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def display_label(self, lang: str | None = None) -> str:
        code = (lang or "").split("-")[0].lower()
        value = getattr(self, f"label_{code}", None)
        return value or self.label_fr or self.label_en or self.label


class CreditBorrower(db.Model):
    __tablename__ = "credit_borrowers"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    sector_id = db.Column(db.Integer, db.ForeignKey("credit_sectors.id", ondelete="SET NULL"), nullable=True, index=True)
    country_id = db.Column(db.Integer, db.ForeignKey("credit_countries.id", ondelete="SET NULL"), nullable=True, index=True)
    rating_id = db.Column(db.Integer, db.ForeignKey("credit_ratings.id", ondelete="SET NULL"), nullable=True, index=True)
    sector = db.Column(db.String(120), nullable=True)
    country = db.Column(db.String(80), nullable=True)
    internal_rating = db.Column(db.String(16), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    sector_ref = db.relationship("CreditSector")
    country_ref = db.relationship("CreditCountry")
    rating_ref = db.relationship("CreditRating")


class CreditDeal(db.Model):
    __tablename__ = "credit_deals"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("credit_borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    code = db.Column(db.String(64), nullable=False, index=True)
    purpose = db.Column(db.String(255), nullable=True)
    requested_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    currency = db.Column(db.String(8), nullable=False, default="EUR")
    status = db.Column(db.String(32), nullable=False, default="in_review", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    borrower = db.relationship("CreditBorrower", backref=db.backref("deals", lazy="dynamic"))


class CreditFacility(db.Model):
    __tablename__ = "credit_facilities"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("credit_deals.id", ondelete="CASCADE"), nullable=False, index=True)
    facility_type_id = db.Column(db.Integer, db.ForeignKey("credit_facility_types.id", ondelete="SET NULL"), nullable=True, index=True)
    facility_type = db.Column(db.String(64), nullable=False, default="term_loan")
    approved_amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    tenor_months = db.Column(db.Integer, nullable=True)
    interest_rate = db.Column(db.Numeric(9, 4), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="draft", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    deal = db.relationship("CreditDeal", backref=db.backref("facilities", lazy="dynamic"))
    facility_type_ref = db.relationship("CreditFacilityType")


class CreditCollateral(db.Model):
    __tablename__ = "credit_collaterals"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("credit_borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("credit_deals.id", ondelete="SET NULL"), nullable=True, index=True)
    collateral_type_id = db.Column(db.Integer, db.ForeignKey("credit_collateral_types.id", ondelete="SET NULL"), nullable=True, index=True)
    collateral_type = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    market_value = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    haircut_pct = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    borrower = db.relationship("CreditBorrower", backref=db.backref("collaterals", lazy="dynamic"))
    deal = db.relationship("CreditDeal", backref=db.backref("collaterals", lazy="dynamic"))
    collateral_type_ref = db.relationship("CreditCollateralType")


class CreditGuarantor(db.Model):
    __tablename__ = "credit_guarantors"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("credit_borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("credit_deals.id", ondelete="SET NULL"), nullable=True, index=True)
    name = db.Column(db.String(180), nullable=False)
    guarantee_type_id = db.Column(db.Integer, db.ForeignKey("credit_guarantee_types.id", ondelete="SET NULL"), nullable=True, index=True)
    guarantee_type = db.Column(db.String(80), nullable=False, default="personal")
    amount = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    borrower = db.relationship("CreditBorrower", backref=db.backref("guarantors", lazy="dynamic"))
    deal = db.relationship("CreditDeal", backref=db.backref("guarantors", lazy="dynamic"))
    guarantee_type_ref = db.relationship("CreditGuaranteeType")


class CreditFinancialStatement(db.Model):
    __tablename__ = "credit_financial_statements"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("credit_borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    period_label = db.Column(db.String(32), nullable=False)
    fiscal_year = db.Column(db.Integer, nullable=False)
    revenue = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    ebitda = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    total_debt = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    cash = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    net_income = db.Column(db.Numeric(18, 2), nullable=False, default=0)
    spreading_status = db.Column(db.String(32), nullable=False, default="in_progress")
    imported_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    analyst_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    analyst_function_id = db.Column(db.Integer, db.ForeignKey("credit_analyst_functions.id", ondelete="SET NULL"), nullable=True, index=True)
    import_source = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    borrower = db.relationship("CreditBorrower", backref=db.backref("financial_statements", lazy="dynamic"))
    imported_by = db.relationship("User", foreign_keys=[imported_by_user_id])
    analyst_user = db.relationship("User", foreign_keys=[analyst_user_id])
    analyst_function_ref = db.relationship("CreditAnalystFunction")


class CreditRatioSnapshot(db.Model):
    __tablename__ = "credit_ratio_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("credit_borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    statement_id = db.Column(db.Integer, db.ForeignKey("credit_financial_statements.id", ondelete="SET NULL"), nullable=True, index=True)
    snapshot_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    dscr = db.Column(db.Numeric(9, 4), nullable=True)
    leverage = db.Column(db.Numeric(9, 4), nullable=True)
    liquidity = db.Column(db.Numeric(9, 4), nullable=True)
    risk_grade = db.Column(db.String(16), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    borrower = db.relationship("CreditBorrower", backref=db.backref("ratio_snapshots", lazy="dynamic"))
    statement = db.relationship("CreditFinancialStatement")


class CreditMemo(db.Model):
    __tablename__ = "credit_memos"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("credit_deals.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("credit_borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    title = db.Column(db.String(180), nullable=False)
    recommendation = db.Column(db.String(64), nullable=False, default="review")
    summary_text = db.Column(db.Text, nullable=False, default="")
    ai_generated = db.Column(db.Boolean, nullable=False, default=False)
    ai_prompt = db.Column(db.Text, nullable=True)
    ai_response_json = db.Column(db.JSON, nullable=True)
    prepared_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    deal = db.relationship("CreditDeal", backref=db.backref("memos", lazy="dynamic"))
    borrower = db.relationship("CreditBorrower", backref=db.backref("memos", lazy="dynamic"))
    prepared_by = db.relationship("User")


class CreditAnalystFunction(db.Model):
    __tablename__ = "credit_analyst_functions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_credit_analyst_function_tenant_code"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    code = db.Column(db.String(64), nullable=False)
    label = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CreditAnalystGroup(db.Model):
    __tablename__ = "credit_analyst_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_credit_analyst_group_tenant_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CreditAnalystGroupMember(db.Model):
    __tablename__ = "credit_analyst_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", "function_name", name="uq_credit_group_member_function"),
    )

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("credit_analyst_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    function_id = db.Column(db.Integer, db.ForeignKey("credit_analyst_functions.id", ondelete="SET NULL"), nullable=True, index=True)
    function_name = db.Column(db.String(64), nullable=False, default="analyst")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    group = db.relationship("CreditAnalystGroup", backref=db.backref("members", lazy="dynamic", cascade="all, delete-orphan"))
    user = db.relationship("User")
    function_ref = db.relationship("CreditAnalystFunction")


class CreditApprovalWorkflowStep(db.Model):
    __tablename__ = "credit_approval_workflow_steps"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = db.Column(db.Integer, nullable=False, default=1, index=True)
    stage = db.Column(db.String(64), nullable=False, default="analyst_review")
    step_name = db.Column(db.String(120), nullable=False, default="")
    group_id = db.Column(db.Integer, db.ForeignKey("credit_analyst_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    function_id = db.Column(db.Integer, db.ForeignKey("credit_analyst_functions.id", ondelete="SET NULL"), nullable=True, index=True)
    function_name = db.Column(db.String(64), nullable=True)
    sla_days = db.Column(db.Integer, nullable=True)
    is_required = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    group = db.relationship("CreditAnalystGroup")
    function_ref = db.relationship("CreditAnalystFunction")


class CreditApproval(db.Model):
    __tablename__ = "credit_approvals"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    memo_id = db.Column(db.Integer, db.ForeignKey("credit_memos.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = db.Column(db.String(64), nullable=False, default="analyst_review")
    decision = db.Column(db.String(32), nullable=False, default="pending")
    comments = db.Column(db.Text, nullable=True)
    workflow_step_id = db.Column(db.Integer, db.ForeignKey("credit_approval_workflow_steps.id", ondelete="SET NULL"), nullable=True, index=True)
    analyst_group_id = db.Column(db.Integer, db.ForeignKey("credit_analyst_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    analyst_function_id = db.Column(db.Integer, db.ForeignKey("credit_analyst_functions.id", ondelete="SET NULL"), nullable=True, index=True)
    analyst_function = db.Column(db.String(64), nullable=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    memo = db.relationship("CreditMemo", backref=db.backref("approvals", lazy="dynamic"))
    workflow_step = db.relationship("CreditApprovalWorkflowStep")
    analyst_group = db.relationship("CreditAnalystGroup")
    analyst_function_ref = db.relationship("CreditAnalystFunction")
    actor_user = db.relationship("User")


class CreditDocument(db.Model):
    __tablename__ = "credit_documents"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("credit_borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("credit_deals.id", ondelete="SET NULL"), nullable=True, index=True)
    memo_id = db.Column(db.Integer, db.ForeignKey("credit_memos.id", ondelete="SET NULL"), nullable=True, index=True)
    title = db.Column(db.String(180), nullable=False)
    doc_type = db.Column(db.String(64), nullable=False, default="supporting")
    file_path = db.Column(db.String(500), nullable=True)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    borrower = db.relationship("CreditBorrower", backref=db.backref("documents", lazy="dynamic"))
    deal = db.relationship("CreditDeal", backref=db.backref("documents", lazy="dynamic"))
    memo = db.relationship("CreditMemo", backref=db.backref("documents", lazy="dynamic"))
    uploaded_by = db.relationship("User")
