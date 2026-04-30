from flask import Blueprint

bp = Blueprint("ml", __name__, url_prefix="/ml")

from . import routes  # noqa: E402,F401
