from flask import Blueprint

bp = Blueprint("finance", __name__, url_prefix="/finance")

from . import routes  # noqa: E402,F401
