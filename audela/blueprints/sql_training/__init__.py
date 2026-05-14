from flask import Blueprint

bp = Blueprint("sql_training", __name__, url_prefix="/sql-training")

from . import routes  # noqa: E402,F401
from . import api_routes  # noqa: E402,F401
