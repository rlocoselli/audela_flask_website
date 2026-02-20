from __future__ import annotations

from datetime import datetime

from ..extensions import db


class Prospect(db.Model):
    __tablename__ = "prospects"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(40), nullable=True)
    company = db.Column(db.String(160), nullable=True)
    solution_interest = db.Column(db.String(120), nullable=True)
    message = db.Column(db.Text, nullable=True)

    rdv_date = db.Column(db.Date, nullable=False, index=True)
    rdv_time = db.Column(db.Time, nullable=False)
    timezone = db.Column(db.String(64), nullable=False, default="Europe/Paris")

    status = db.Column(db.String(24), nullable=False, default="new")  # new|confirmed|done|cancelled
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Prospect id={self.id} email={self.email} rdv={self.rdv_date} {self.rdv_time}>"
