from __future__ import annotations

from datetime import datetime

from ..extensions import db


class TenantScopedMixin:
    """Mixin for application DB entities that must be isolated per tenant.

    IMPORTANT: enforcement must happen in the service layer (queries filtered by current tenant)
    and in the DB through constraints where possible.
    """

    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)


class DataSource(TenantScopedMixin, db.Model):
    __tablename__ = "data_sources"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(32), nullable=False)  # postgres/mysql/sqlserver/oracle...

    # Encrypted JSON config (host, port, dbname, username, etc.)
    config_encrypted = db.Column(db.LargeBinary, nullable=False)

    # JSON policy: timeouts, row limits, schema whitelists...
    policy_json = db.Column(db.JSON, nullable=False, default=dict)

    name = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Collection(TenantScopedMixin, db.Model):
    __tablename__ = "collections"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)
    name = db.Column(db.String(128), nullable=False)

    # MVP: ACL stored as JSON; evolve to normalized ACL tables later
    acl_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    parent = db.relationship("Collection", remote_side=[id], backref=db.backref("children", lazy="dynamic"))


class Question(TenantScopedMixin, db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False)
    collection_id = db.Column(db.Integer, db.ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)

    name = db.Column(db.String(128), nullable=False)
    sql_text = db.Column(db.Text, nullable=False)

    # JSON schema for parameters: {"data_inicio": {"type": "date", ...}}
    params_schema_json = db.Column(db.JSON, nullable=False, default=dict)
    viz_config_json = db.Column(db.JSON, nullable=False, default=dict)

    acl_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    data_source = db.relationship("DataSource")
    collection = db.relationship("Collection")


class Dashboard(TenantScopedMixin, db.Model):
    __tablename__ = "dashboards"

    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)

    name = db.Column(db.String(128), nullable=False)
    layout_json = db.Column(db.JSON, nullable=False, default=dict)
    filters_json = db.Column(db.JSON, nullable=False, default=dict)
    acl_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    collection = db.relationship("Collection")


class DashboardCard(TenantScopedMixin, db.Model):
    __tablename__ = "dashboard_cards"

    id = db.Column(db.Integer, primary_key=True)
    dashboard_id = db.Column(db.Integer, db.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False)

    viz_config_json = db.Column(db.JSON, nullable=False, default=dict)
    position_json = db.Column(db.JSON, nullable=False, default=dict)  # grid positioning

    dashboard = db.relationship("Dashboard", backref=db.backref("cards", lazy="dynamic"))
    question = db.relationship("Question")


class QueryRun(TenantScopedMixin, db.Model):
    __tablename__ = "query_runs"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    duration_ms = db.Column(db.Integer, nullable=True)
    rows = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="running")
    error = db.Column(db.Text, nullable=True)


class AuditEvent(TenantScopedMixin, db.Model):
    __tablename__ = "audit_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    event_type = db.Column(db.String(64), nullable=False)
    payload_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
