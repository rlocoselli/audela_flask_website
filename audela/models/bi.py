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
    base_url = db.Column(db.String(300), nullable=True)
    method = db.Column(db.String(300), nullable=True)
    
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

    # Mark a dashboard as the tenant's primary/default dashboard
    is_primary = db.Column(db.Boolean, nullable=False, default=False, index=True)

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


# -----------------------------
# Reports (Crystal-like builder)
# -----------------------------


class Report(TenantScopedMixin, db.Model):
    """A saved report definition with a drag-and-drop layout."""

    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False)

    name = db.Column(db.String(128), nullable=False)

    # Layout JSON stores sections/blocks positions and configuration.
    layout_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    data_source = db.relationship("DataSource")


class ReportBlock(TenantScopedMixin, db.Model):
    """Reusable blocks that can be placed in a report layout."""

    __tablename__ = "report_blocks"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)

    # text / question (table/chart) / markdown
    block_type = db.Column(db.String(32), nullable=False, default="text")

    # For block_type == question
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)

    title = db.Column(db.String(200), nullable=True)
    config_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    report = db.relationship("Report", backref=db.backref("blocks", lazy="dynamic"))
    question = db.relationship("Question")


# -----------------------------
# BI Files (uploads, URL, S3)
# -----------------------------


class FileFolder(TenantScopedMixin, db.Model):
    """Tenant-scoped folders to organize uploaded files in a tree view."""

    __tablename__ = "file_folders"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("file_folders.id", ondelete="CASCADE"), nullable=True)
    name = db.Column(db.String(200), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship("FileFolder", remote_side=[id], backref=db.backref("children", lazy="dynamic"))


class FileAsset(TenantScopedMixin, db.Model):
    """A file available as a BI datasource (CSV/Excel/Parquet).

    Files can come from:
    - direct upload
    - URL download
    - AWS S3 object download
    """

    __tablename__ = "file_assets"

    id = db.Column(db.Integer, primary_key=True)
    folder_id = db.Column(db.Integer, db.ForeignKey("file_folders.id", ondelete="SET NULL"), nullable=True)

    # Display name (can differ from original filename)
    name = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)

    # upload | url | s3
    source_type = db.Column(db.String(32), nullable=False, default="upload")

    # csv | excel | parquet
    file_format = db.Column(db.String(32), nullable=False)

    # Relative path in tenant storage root.
    storage_path = db.Column(db.String(500), nullable=False)

    size_bytes = db.Column(db.Integer, nullable=True)
    sha256 = db.Column(db.String(64), nullable=True)

    # Optional encrypted config for URL/S3 connector metadata (not required for direct uploads).
    config_encrypted = db.Column(db.LargeBinary, nullable=True)

    # Cached schema for autocomplete: {"columns": [{"name":..., "type":...}, ...]}
    schema_json = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    folder = db.relationship("FileFolder")
