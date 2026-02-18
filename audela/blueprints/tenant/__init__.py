"""
Tenant Management Blueprint

Gestion complète du tenant: login, signup, utilisateurs, abonnements.
"""
from flask import Blueprint

bp = Blueprint("tenant", __name__, url_prefix="/tenant")

from . import routes
