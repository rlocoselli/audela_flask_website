"""E-Learning Blueprint - Multi-subject learning platform with gamification."""

from flask import Blueprint

bp = Blueprint(
    "e_learning",
    __name__,
    url_prefix="/e-learning",
    template_folder="templates",
    static_folder="static",
)

from . import api_routes, routes

__all__ = ["bp"]
