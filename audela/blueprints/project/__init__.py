from flask import Blueprint

bp = Blueprint("project", __name__, url_prefix="/project")

from . import routes  # noqa: E402,F401
