from flask import Blueprint

bp = Blueprint("ifrs9", __name__, url_prefix="/ifrs9")

from . import routes  # noqa: E402,F401
