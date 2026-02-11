from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class ApiSource(db.Model):
    __tablename__ = "api_sources"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    base_url = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), default="GET")
    headers = db.Column(db.JSON, nullable=True)
    params = db.Column(db.JSON, nullable=True)
    auth_type = db.Column(db.String(50), nullable=True)
    auth_token = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)