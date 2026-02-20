from __future__ import annotations

from datetime import datetime

from ..extensions import db


class ProjectWorkspace(db.Model):
    __tablename__ = "project_workspaces"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    state_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship("Tenant", backref=db.backref("project_workspace", uselist=False, lazy="select"))
    updated_by_user = db.relationship("User", lazy="select")

    def __repr__(self) -> str:
        return f"<ProjectWorkspace tenant_id={self.tenant_id}>"
