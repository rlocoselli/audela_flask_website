from __future__ import annotations

from datetime import datetime

from ..extensions import db


class PublicPageVisit(db.Model):
    """Persist public website page views for platform analytics."""

    __tablename__ = "public_page_visits"

    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(120), nullable=True, index=True)
    path = db.Column(db.String(255), nullable=False, index=True)
    visitor_id = db.Column(db.String(64), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_hash = db.Column(db.String(64), nullable=True, index=True)
    referrer = db.Column(db.String(255), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    utm_source = db.Column(db.String(120), nullable=True)
    utm_medium = db.Column(db.String(120), nullable=True)
    utm_campaign = db.Column(db.String(120), nullable=True)
    is_home = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<PublicPageVisit path={self.path} visitor={self.visitor_id}>"
