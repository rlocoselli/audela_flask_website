from flask import Blueprint

bp = Blueprint("finance", __name__, url_prefix="/finance")

from . import routes  # noqa: E402,F401
from . import finance_master_data  # noqa: E402,F401
