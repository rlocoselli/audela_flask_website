from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import abort
from flask_login import current_user

F = TypeVar("F", bound=Callable)


def require_roles(*roles: str) -> Callable[[F], F]:
    """Decorator for RBAC checks.

    For finer-grained checks (collection/dashboard/question), implement ACL check in service layer.
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if roles and not any(current_user.has_role(r) for r in roles):
                abort(403)
            return fn(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator
