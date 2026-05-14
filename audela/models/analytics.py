"""Internal Analytics Models

Tracks page views and feature usage by authenticated users for admin insights.
"""

from __future__ import annotations
from datetime import datetime
from ..extensions import db


class InternalPageView(db.Model):
    """Tracks page views from authenticated (and anonymous) users."""

    __tablename__ = "internal_page_views"

    id = db.Column(db.Integer, primary_key=True)
    # Route/endpoint info
    endpoint = db.Column(db.String(120), nullable=True, index=True)
    path = db.Column(db.String(512), nullable=False, index=True)
    blueprint = db.Column(db.String(64), nullable=True, index=True)
    # User info (nullable for anonymous)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    # Request info
    method = db.Column(db.String(8), nullable=False, default="GET")
    status_code = db.Column(db.Integer, nullable=True)
    duration_ms = db.Column(db.Float, nullable=True)
    # Session & locale
    session_id = db.Column(db.String(64), nullable=True, index=True)
    language_code = db.Column(db.String(12), nullable=True)
    # Network
    ip_hash = db.Column(db.String(64), nullable=True)
    user_agent_short = db.Column(db.String(128), nullable=True)
    is_mobile = db.Column(db.Boolean, nullable=False, default=False)
    # Referrer (internal vs external)
    referrer_path = db.Column(db.String(512), nullable=True)
    is_internal_nav = db.Column(db.Boolean, nullable=False, default=False)
    # Time
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship("User", foreign_keys=[user_id])
    tenant = db.relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self) -> str:
        return f"<InternalPageView {self.method} {self.path} [{self.status_code}]>"


class FeatureUsageEvent(db.Model):
    """Tracks specific feature interactions (API calls, actions, downloads, etc.)."""

    __tablename__ = "feature_usage_events"

    id = db.Column(db.Integer, primary_key=True)
    # Feature identification
    feature = db.Column(db.String(64), nullable=False, index=True)   # e.g. "e_learning"
    action = db.Column(db.String(64), nullable=False, index=True)    # e.g. "submit_exercise", "download_cert"
    label = db.Column(db.String(128), nullable=True)                  # e.g. "sql101-les1-ex1"
    numeric_value = db.Column(db.Float, nullable=True)               # e.g. score, points, duration_s
    # User context
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    # Extra JSON payload
    extra = db.Column(db.JSON, nullable=True)
    # Time
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship("User", foreign_keys=[user_id])
    tenant = db.relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self) -> str:
        return f"<FeatureUsageEvent {self.feature}.{self.action}>"
