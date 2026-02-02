from flask import Blueprint

bp = Blueprint("portal", __name__, url_prefix="/app")

from . import routes  # noqa: E402,F401
