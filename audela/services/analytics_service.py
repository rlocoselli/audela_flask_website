"""Internal Analytics Service

Helpers for recording page views and feature events,
and querying aggregated analytics for the admin dashboard.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta
from typing import Any

from flask import request, g, session
from flask_login import current_user
from sqlalchemy import func, text

from ..extensions import db
from ..models.analytics import InternalPageView, FeatureUsageEvent


# ---------------------------------------------------------------------------
# Recording helpers
# ---------------------------------------------------------------------------

def _hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


def _user_agent_short(ua: str | None) -> str | None:
    if not ua:
        return None
    # Truncate to 128 chars and tag as mobile if likely
    return ua[:128]


def _is_mobile(ua: str | None) -> bool:
    if not ua:
        return False
    ua_lower = ua.lower()
    return any(kw in ua_lower for kw in ("mobile", "android", "iphone", "ipad"))


def record_page_view(
    endpoint: str | None = None,
    path: str | None = None,
    blueprint: str | None = None,
    status_code: int = 200,
    duration_ms: float | None = None,
) -> None:
    """Record an internal page view. Safe to call — swallows all errors."""
    try:
        req_path = path or request.path
        ua_raw = request.headers.get("User-Agent")
        referrer_raw = request.referrer

        # Determine if navigation was internal (from same host)
        host = request.host
        is_internal = bool(referrer_raw and host in referrer_raw)
        referrer_path = None
        if referrer_raw:
            from urllib.parse import urlsplit
            parts = urlsplit(referrer_raw)
            referrer_path = parts.path[:512] if parts.path else None

        user_id = current_user.id if current_user.is_authenticated else None
        tenant_id = getattr(current_user, "tenant_id", None) if current_user.is_authenticated else None
        lang = getattr(g, "lang", session.get("lang", "en"))

        pv = InternalPageView(
            endpoint=endpoint or request.endpoint,
            path=req_path,
            blueprint=blueprint or request.blueprint,
            user_id=user_id,
            tenant_id=tenant_id,
            method=request.method,
            status_code=status_code,
            duration_ms=duration_ms,
            session_id=session.get("_id"),
            language_code=lang,
            ip_hash=_hash_ip(request.remote_addr),
            user_agent_short=_user_agent_short(ua_raw),
            is_mobile=_is_mobile(ua_raw),
            referrer_path=referrer_path,
            is_internal_nav=is_internal,
        )
        db.session.add(pv)
        db.session.commit()
    except Exception:
        db.session.rollback()


def track_event(
    feature: str,
    action: str,
    label: str | None = None,
    numeric_value: float | None = None,
    extra: dict | None = None,
) -> None:
    """Record a feature usage event. Safe to call — swallows all errors."""
    try:
        user_id = current_user.id if current_user.is_authenticated else None
        tenant_id = getattr(current_user, "tenant_id", None) if current_user.is_authenticated else None

        evt = FeatureUsageEvent(
            feature=feature,
            action=action,
            label=label,
            numeric_value=numeric_value,
            user_id=user_id,
            tenant_id=tenant_id,
            extra=extra,
        )
        db.session.add(evt)
        db.session.commit()
    except Exception:
        db.session.rollback()


# ---------------------------------------------------------------------------
# Analytics query helpers
# ---------------------------------------------------------------------------

def _days_ago(n: int) -> datetime:
    return datetime.utcnow() - timedelta(days=n)


def get_page_views_summary(days: int = 30) -> dict:
    """Top pages by view count over last N days."""
    since = _days_ago(days)

    total = db.session.query(func.count(InternalPageView.id)).filter(
        InternalPageView.created_at >= since
    ).scalar() or 0

    unique_users = db.session.query(
        func.count(func.distinct(InternalPageView.user_id))
    ).filter(
        InternalPageView.created_at >= since,
        InternalPageView.user_id.isnot(None),
    ).scalar() or 0

    top_pages = db.session.query(
        InternalPageView.path,
        InternalPageView.blueprint,
        func.count(InternalPageView.id).label("views"),
        func.count(func.distinct(InternalPageView.user_id)).label("unique_users"),
    ).filter(
        InternalPageView.created_at >= since,
        InternalPageView.method == "GET",
    ).group_by(
        InternalPageView.path, InternalPageView.blueprint
    ).order_by(
        func.count(InternalPageView.id).desc()
    ).limit(20).all()

    # Daily views (last N days)
    daily = db.session.query(
        func.date(InternalPageView.created_at).label("day"),
        func.count(InternalPageView.id).label("views"),
    ).filter(
        InternalPageView.created_at >= since,
    ).group_by(
        func.date(InternalPageView.created_at)
    ).order_by(
        func.date(InternalPageView.created_at)
    ).all()

    # Top blueprints
    blueprints = db.session.query(
        InternalPageView.blueprint,
        func.count(InternalPageView.id).label("views"),
    ).filter(
        InternalPageView.created_at >= since,
        InternalPageView.blueprint.isnot(None),
    ).group_by(InternalPageView.blueprint).order_by(
        func.count(InternalPageView.id).desc()
    ).limit(10).all()

    # Mobile vs desktop
    mobile_count = db.session.query(func.count(InternalPageView.id)).filter(
        InternalPageView.created_at >= since,
        InternalPageView.is_mobile == True,  # noqa: E712
    ).scalar() or 0

    return {
        "total_views": total,
        "unique_users": unique_users,
        "mobile_pct": round(mobile_count / total * 100, 1) if total else 0,
        "top_pages": [
            {
                "path": r.path,
                "blueprint": r.blueprint,
                "views": r.views,
                "unique_users": r.unique_users,
            }
            for r in top_pages
        ],
        "daily": [{"day": str(r.day), "views": r.views} for r in daily],
        "blueprints": [{"blueprint": r.blueprint or "root", "views": r.views} for r in blueprints],
    }


def get_feature_usage_summary(days: int = 30) -> dict:
    """Feature usage breakdown over last N days."""
    since = _days_ago(days)

    # Top features
    features = db.session.query(
        FeatureUsageEvent.feature,
        func.count(FeatureUsageEvent.id).label("events"),
        func.count(func.distinct(FeatureUsageEvent.user_id)).label("unique_users"),
    ).filter(
        FeatureUsageEvent.created_at >= since
    ).group_by(FeatureUsageEvent.feature).order_by(
        func.count(FeatureUsageEvent.id).desc()
    ).all()

    # Top actions per feature
    actions = db.session.query(
        FeatureUsageEvent.feature,
        FeatureUsageEvent.action,
        func.count(FeatureUsageEvent.id).label("events"),
    ).filter(
        FeatureUsageEvent.created_at >= since
    ).group_by(
        FeatureUsageEvent.feature, FeatureUsageEvent.action
    ).order_by(func.count(FeatureUsageEvent.id).desc()).limit(30).all()

    # Daily events
    daily = db.session.query(
        func.date(FeatureUsageEvent.created_at).label("day"),
        func.count(FeatureUsageEvent.id).label("events"),
    ).filter(
        FeatureUsageEvent.created_at >= since
    ).group_by(
        func.date(FeatureUsageEvent.created_at)
    ).order_by(func.date(FeatureUsageEvent.created_at)).all()

    # E-learning specific: most used exercises
    e_learning_exercises = db.session.query(
        FeatureUsageEvent.label,
        func.count(FeatureUsageEvent.id).label("attempts"),
        func.avg(FeatureUsageEvent.numeric_value).label("avg_score"),
    ).filter(
        FeatureUsageEvent.created_at >= since,
        FeatureUsageEvent.feature == "e_learning",
        FeatureUsageEvent.action == "submit_exercise",
        FeatureUsageEvent.label.isnot(None),
    ).group_by(FeatureUsageEvent.label).order_by(
        func.count(FeatureUsageEvent.id).desc()
    ).limit(10).all()

    return {
        "features": [
            {
                "feature": r.feature,
                "events": r.events,
                "unique_users": r.unique_users,
            }
            for r in features
        ],
        "actions": [
            {
                "feature": r.feature,
                "action": r.action,
                "events": r.events,
            }
            for r in actions
        ],
        "daily": [{"day": str(r.day), "events": r.events} for r in daily],
        "e_learning_top_exercises": [
            {
                "label": r.label,
                "attempts": r.attempts,
                "avg_score": round(r.avg_score or 0, 1),
            }
            for r in e_learning_exercises
        ],
    }


def get_active_users(days: int = 7) -> list[dict]:
    """Most active users over last N days."""
    since = _days_ago(days)

    from ..models.core import User

    rows = db.session.query(
        InternalPageView.user_id,
        func.count(InternalPageView.id).label("page_views"),
        func.max(InternalPageView.created_at).label("last_seen"),
    ).filter(
        InternalPageView.created_at >= since,
        InternalPageView.user_id.isnot(None),
    ).group_by(InternalPageView.user_id).order_by(
        func.count(InternalPageView.id).desc()
    ).limit(20).all()

    result = []
    for row in rows:
        user = User.query.get(row.user_id)
        event_count = db.session.query(func.count(FeatureUsageEvent.id)).filter(
            FeatureUsageEvent.user_id == row.user_id,
            FeatureUsageEvent.created_at >= since,
        ).scalar() or 0

        if user and getattr(user, "email", None):
            display_name = user.email.split("@")[0]
        else:
            display_name = f"User#{row.user_id}"

        result.append({
            "user_id": row.user_id,
            "username": display_name,
            "email": user.email if user else "",
            "page_views": row.page_views,
            "feature_events": event_count,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        })

    return result
