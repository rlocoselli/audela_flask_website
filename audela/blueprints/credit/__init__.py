from flask import Blueprint

bp = Blueprint("credit", __name__, url_prefix="/credit")

from . import routes  # noqa: E402,F401
