"""
SQL Training Routes - Public portal for SQL training modules
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import abort, flash, g, redirect, render_template, request, url_for, jsonify
from flask_login import current_user, login_required
from sqlalchemy import func

from ...extensions import db
from ...i18n import DEFAULT_LANG, SUPPORTED_LANGS, tr
from ...models.core import User
from ...models.sql_training import (
    SQLTrainingModule,
    SQLTrainingLesson,
    SQLTrainingExercise,
    UserSQLTrainingEnrollment,
    UserSQLTrainingSubmission,
    SQLTrainingCertificate,
    SQLTrainingSampleDatabase,
)
from ...security import require_roles
from ...tenancy import get_current_tenant_id, get_user_module_access
from ...services.sql_training_service import SQLTrainingService

from . import bp

logger = logging.getLogger(__name__)


def get_lang():
    """Get current user language from session or default."""
    if current_user.is_authenticated:
        lang = request.args.get("lang") or request.cookies.get("lang")
    else:
        lang = request.args.get("lang")
    
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    return lang


def translate_field(obj, field_name, lang=None):
    """Helper to translate i18n fields."""
    if lang is None:
        lang = get_lang()
    
    if not hasattr(obj, field_name):
        return ""
    
    field_data = getattr(obj, field_name)
    if isinstance(field_data, dict):
        return field_data.get(lang, field_data.get(DEFAULT_LANG, ""))
    return str(field_data)


@bp.route("/", methods=["GET"])
def modules_list():
    """List all available SQL training modules."""
    lang = get_lang()
    
    # Get all active modules
    modules = SQLTrainingModule.query.filter_by(is_active=True).order_by(
        SQLTrainingModule.level, SQLTrainingModule.order
    ).all()
    
    # Get user enrollments if logged in
    user_enrollments = {}
    if current_user.is_authenticated:
        enrollments = UserSQLTrainingEnrollment.query.filter_by(user_id=current_user.id).all()
        user_enrollments = {e.module_id: e for e in enrollments}
    
    return render_template(
        "sql_training/modules_list.html",
        modules=modules,
        user_enrollments=user_enrollments,
        lang=lang,
        translate=translate_field,
    )


@bp.route("/module/<int:module_id>", methods=["GET"])
@login_required
def module_detail(module_id: int):
    """View module details and start learning."""
    lang = get_lang()
    
    module = SQLTrainingModule.query.get_or_404(module_id)
    if not module.is_active:
        abort(404)
    
    # Get or create enrollment
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first()
    
    if not enrollment:
        # Auto-enroll user
        enrollment = UserSQLTrainingEnrollment(
            user_id=current_user.id,
            module_id=module_id,
            status="in_progress"
        )
        db.session.add(enrollment)
        db.session.commit()
        flash(f"Enrolled in {translate_field(module, 'title_i18n', lang)}", "success")
    
    # Get lessons
    lessons = SQLTrainingLesson.query.filter_by(
        module_id=module_id, is_active=True
    ).order_by(SQLTrainingLesson.order).all()
    
    # Initialize sample database if needed
    service = SQLTrainingService()
    sample_db = service.get_or_create_sample_database(current_user.id, module_id)
    
    return render_template(
        "sql_training/module_detail.html",
        module=module,
        lessons=lessons,
        enrollment=enrollment,
        sample_db=sample_db,
        lang=lang,
        translate=translate_field,
    )


@bp.route("/lesson/<int:lesson_id>", methods=["GET"])
@login_required
def lesson_view(lesson_id: int):
    """View lesson content and exercises."""
    lang = get_lang()
    
    lesson = SQLTrainingLesson.query.get_or_404(lesson_id)
    if not lesson.is_active:
        abort(404)
    
    module = lesson.module
    
    # Get enrollment
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module.id
    ).first_or_404()
    
    # Get exercises
    exercises = SQLTrainingExercise.query.filter_by(
        lesson_id=lesson_id, is_active=True
    ).order_by(SQLTrainingExercise.order).all()
    
    # Get user's submissions for this lesson
    submissions_by_exercise = {}
    for exercise in exercises:
        last_submission = UserSQLTrainingSubmission.query.filter_by(
            enrollment_id=enrollment.id,
            exercise_id=exercise.id
        ).order_by(UserSQLTrainingSubmission.submitted_at.desc()).first()
        submissions_by_exercise[exercise.id] = last_submission
    
    return render_template(
        "sql_training/lesson_view.html",
        lesson=lesson,
        module=module,
        exercises=exercises,
        enrollment=enrollment,
        submissions_by_exercise=submissions_by_exercise,
        lang=lang,
        translate=translate_field,
    )


@bp.route("/exercise/<int:exercise_id>", methods=["GET"])
@login_required
def exercise_view(exercise_id: int):
    """View exercise for practice."""
    lang = get_lang()
    
    exercise = SQLTrainingExercise.query.get_or_404(exercise_id)
    if not exercise.is_active:
        abort(404)
    
    lesson = exercise.lesson
    module = lesson.module
    
    # Get enrollment
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module.id
    ).first_or_404()
    
    # Get previous submissions
    submissions = UserSQLTrainingSubmission.query.filter_by(
        enrollment_id=enrollment.id,
        exercise_id=exercise_id
    ).order_by(UserSQLTrainingSubmission.submitted_at.desc()).all()
    
    return render_template(
        "sql_training/exercise_editor.html",
        exercise=exercise,
        lesson=lesson,
        module=module,
        enrollment=enrollment,
        submissions=submissions,
        lang=lang,
        translate=translate_field,
    )


@bp.route("/certificate/<int:certificate_id>", methods=["GET"])
def certificate_view(certificate_id: int):
    """View certificate (public)."""
    certificate = SQLTrainingCertificate.query.get_or_404(certificate_id)
    
    if not certificate.is_public:
        abort(404)
    
    lang = get_lang()
    
    return render_template(
        "sql_training/certificate_view.html",
        certificate=certificate,
        lang=lang,
        translate=translate_field,
    )


@bp.route("/verify-certificate/<verification_code>", methods=["GET"])
def verify_certificate(verification_code: str):
    """Verify certificate authenticity."""
    certificate = SQLTrainingCertificate.query.filter_by(
        verification_code=verification_code
    ).first_or_404()
    
    lang = get_lang()
    
    return render_template(
        "sql_training/certificate_verify.html",
        certificate=certificate,
        lang=lang,
        translate=translate_field,
    )


@bp.route("/dashboard", methods=["GET"])
@login_required
def user_dashboard():
    """User's SQL training dashboard with progress."""
    lang = get_lang()
    
    # Get all enrollments
    enrollments = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id
    ).all()
    
    # Get certificates
    certificates = SQLTrainingCertificate.query.filter_by(
        user_id=current_user.id
    ).order_by(SQLTrainingCertificate.issued_at.desc()).all()
    
    return render_template(
        "sql_training/user_dashboard.html",
        enrollments=enrollments,
        certificates=certificates,
        lang=lang,
        translate=translate_field,
    )


@bp.route("/database-diagram/<int:module_id>", methods=["GET"])
@login_required
def database_diagram(module_id: int):
    """Show database diagram for the module."""
    lang = get_lang()
    
    module = SQLTrainingModule.query.get_or_404(module_id)
    if not module.is_active:
        abort(404)
    
    # Verify enrollment
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first_or_404()
    
    # Get database schema
    service = SQLTrainingService()
    schema_info = service.get_database_schema(module_id, current_user.id)
    
    return render_template(
        "sql_training/database_diagram.html",
        module=module,
        schema_info=schema_info,
        lang=lang,
        translate=translate_field,
    )
