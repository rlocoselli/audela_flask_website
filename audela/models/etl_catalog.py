from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from audela.extensions import db

from audela.models.core import Tenant

class ETLConnection(db.Model):
    __tablename__ = "etl_connections"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # e.g. postgres, mssql, http
    encrypted_payload = db.Column(db.Text, nullable=False)
    tenant = db.relationship('Tenant', lazy='joined')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ETLConnection {self.name} ({self.type})>"
