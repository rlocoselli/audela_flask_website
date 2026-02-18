"""
Billing Blueprint

Gestion des abonnements, plans tarifaires, paiements Stripe.
"""
from flask import Blueprint

bp = Blueprint("billing", __name__, url_prefix="/billing")

from . import routes
