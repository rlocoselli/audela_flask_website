"""E-Learning UI Routes."""

from flask import render_template, redirect, url_for, request, session, flash
from flask_login import login_required, current_user
from sqlalchemy import desc

from ...extensions import db
from ...models.e_learning import (
    ELearningSubject,
    ELearningModule,
    ELearningLesson,
    ELearningExercise,
    UserELearningEnrollment,
    UserELearningProfile,
    UserAchievement,
    Achievement,
    ELearningCertificate,
    UserELearningSubmission,
)
from ...i18n import tr, normalize_lang
from . import bp


def get_user_language():
    """Get current user's language preference."""
    if current_user.is_authenticated:
        profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
        if profile:
            return normalize_lang(profile.preferred_language)
    return normalize_lang(session.get("language", "pt"))


@bp.route("/", methods=["GET"])
def subjects_list():
    """Browse all learning subjects (SQL, Python, Machine Learning, etc.)."""
    subjects = ELearningSubject.query.filter_by(is_active=True).order_by(ELearningSubject.order).all()
    
    # Get user stats if logged in
    user_stats = {}
    if current_user.is_authenticated:
        profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
        user_stats = {
            "total_points": profile.total_points if profile else 0,
            "current_level": profile.current_level if profile else 1,
            "modules_completed": profile.modules_completed if profile else 0,
        }
    
    return render_template(
        "e_learning/subjects_list.html",
        subjects=subjects,
        user_stats=user_stats,
        page_title=tr("e_learning_subjects"),
    )


@bp.route("/subject/<int:subject_id>", methods=["GET"])
def subject_detail(subject_id):
    """View all modules in a subject."""
    subject = ELearningSubject.query.get_or_404(subject_id)
    modules = ELearningModule.query.filter_by(subject_id=subject_id, is_active=True).order_by(ELearningModule.order).all()
    
    # Get enrollment status for each module
    enrollments = {}
    if current_user.is_authenticated:
        for enrollment in UserELearningEnrollment.query.filter_by(user_id=current_user.id).all():
            enrollments[enrollment.module_id] = enrollment
    
    return render_template(
        "e_learning/subject_detail.html",
        subject=subject,
        modules=modules,
        enrollments=enrollments,
        page_title=subject.name_i18n.get(get_user_language(), subject.name_i18n.get("en", subject.code)),
    )


@bp.route("/module/<int:module_id>", methods=["GET", "POST"])
@login_required
def module_detail(module_id):
    """View module details and enroll user."""
    module = ELearningModule.query.get(module_id)
    if not module:
        flash(tr("Requested module was not found. Showing available modules instead."), "warning")
        return redirect(url_for("e_learning.subjects_list"))
    subject = module.subject
    lessons = ELearningLesson.query.filter_by(module_id=module_id, is_active=True).order_by(ELearningLesson.order).all()
    
    # Auto-enroll on visit
    enrollment = UserELearningEnrollment.query.filter_by(
        user_id=current_user.id, module_id=module_id
    ).first()
    
    if not enrollment:
        enrollment = UserELearningEnrollment(
            user_id=current_user.id,
            module_id=module_id,
            status="in_progress"
        )
        db.session.add(enrollment)
        db.session.commit()
        flash(tr("enrolled_in_module"), "success")
    
    # Get user profile for gamification display
    profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserELearningProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()
    
    return render_template(
        "e_learning/module_detail.html",
        module=module,
        subject=subject,
        lessons=lessons,
        enrollment=enrollment,
        profile=profile,
        page_title=module.title_i18n.get(get_user_language(), module.title_i18n.get("en", module.code)),
    )


@bp.route("/lesson/<int:lesson_id>", methods=["GET"])
@login_required
def lesson_view(lesson_id):
    """View lesson content and exercises."""
    lesson = ELearningLesson.query.get(lesson_id)
    if not lesson:
        flash(tr("Requested lesson was not found. Redirected to your dashboard."), "warning")
        return redirect(url_for("e_learning.dashboard"))
    module = lesson.module
    exercises = ELearningExercise.query.filter_by(lesson_id=lesson_id, is_active=True).order_by(ELearningExercise.order).all()
    
    # Get enrollment
    enrollment = UserELearningEnrollment.query.filter_by(
        user_id=current_user.id, module_id=module.id
    ).first_or_404()
    
    return render_template(
        "e_learning/lesson_view.html",
        lesson=lesson,
        module=module,
        exercises=exercises,
        enrollment=enrollment,
        page_title=lesson.title_i18n.get(get_user_language(), lesson.title_i18n.get("en", lesson.code)),
    )


@bp.route("/exercise/<int:exercise_id>", methods=["GET"])
@login_required
def exercise_view(exercise_id):
    """Interactive SQL/code editor for exercise."""
    exercise = ELearningExercise.query.get(exercise_id)
    if not exercise:
        flash(tr("Requested exercise was not found. Redirected to your dashboard."), "warning")
        return redirect(url_for("e_learning.dashboard"))
    lesson = exercise.lesson
    module = lesson.module
    
    # Get enrollment
    enrollment = UserELearningEnrollment.query.filter_by(
        user_id=current_user.id, module_id=module.id
    ).first_or_404()
    
    # Get previous submissions
    submissions = UserELearningSubmission.query.filter_by(
        user_id=current_user.id, exercise_id=exercise_id
    ).order_by(desc(UserELearningSubmission.submitted_at)).limit(5).all()
    
    return render_template(
        "e_learning/exercise_editor.html",
        exercise=exercise,
        lesson=lesson,
        module=module,
        enrollment=enrollment,
        submissions=submissions,
        page_title=f"{module.title_i18n.get(get_user_language(), module.code)} - {exercise.title_i18n.get(get_user_language(), exercise.code)}",
    )


@bp.route("/user/profile", methods=["GET"])
@login_required
def user_profile():
    """User profile with achievements, stats, and progress."""
    profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserELearningProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()
    
    # Get achievements
    achievements = db.session.query(UserAchievement, Achievement).join(
        Achievement
    ).filter(
        UserAchievement.profile_id == profile.id
    ).all()
    
    # Get enrollments
    enrollments = UserELearningEnrollment.query.filter_by(user_id=current_user.id).all()
    
    # Get certificates
    certificates = ELearningCertificate.query.filter_by(user_id=current_user.id).all()
    
    return render_template(
        "e_learning/user_profile.html",
        profile=profile,
        achievements=achievements,
        enrollments=enrollments,
        certificates=certificates,
        page_title=tr("my_achievements"),
    )


@bp.route("/leaderboard", methods=["GET"])
def leaderboard():
    """Global leaderboard showing top learners."""
    page = request.args.get("page", 1, type=int)
    per_page = 50
    
    # Get top users by points
    top_users = UserELearningProfile.query.order_by(
        UserELearningProfile.total_points.desc()
    ).paginate(page=page, per_page=per_page)
    
    # Get current user rank if authenticated
    user_rank = None
    if current_user.is_authenticated:
        user_profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
        if user_profile:
            user_rank = db.session.query(
                db.func.count(UserELearningProfile.id) + 1
            ).filter(
                UserELearningProfile.total_points > user_profile.total_points
            ).scalar()
    
    return render_template(
        "e_learning/leaderboard.html",
        top_users=top_users,
        user_rank=user_rank,
        page_title=tr("leaderboard"),
    )


@bp.route("/certificate/<int:cert_id>", methods=["GET"])
def certificate_view(cert_id):
    """View and share certificate."""
    cert = ELearningCertificate.query.get(cert_id)
    if not cert:
        flash(tr("Certificate not found."), "warning")
        return redirect(url_for("e_learning.subjects_list"))
    
    # Verify visibility
    if not cert.is_public and (not current_user.is_authenticated or cert.user_id != current_user.id):
        flash(tr("Certificate is private or unavailable."), "warning")
        return redirect(url_for("e_learning.subjects_list"))
    
    # Increment view count
    cert.viewed_count += 1
    db.session.commit()
    
    return render_template(
        "e_learning/certificate_view.html",
        certificate=cert,
        page_title=f"{tr('certificate')} - {cert.module.title_i18n.get(get_user_language(), cert.module.code)}",
    )


@bp.route("/certificate/verify/<code>", methods=["GET"])
def verify_certificate(code):
    """Public certificate verification page."""
    cert = ELearningCertificate.query.filter_by(verification_code=code).first()
    is_valid = bool(cert and cert.is_public)
    
    return render_template(
        "e_learning/certificate_verify.html",
        certificate=cert,
        is_valid=is_valid,
        page_title=tr("verify_certificate"),
    )


@bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    """User's learning dashboard."""
    profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserELearningProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()
    
    # Get recent enrollments
    enrollments = UserELearningEnrollment.query.filter_by(
        user_id=current_user.id
    ).order_by(UserELearningEnrollment.updated_at.desc()).all()
    
    # Get recent certificates
    certificates = ELearningCertificate.query.filter_by(
        user_id=current_user.id
    ).order_by(ELearningCertificate.issued_at.desc()).limit(5).all()
    
    # Get recommended modules
    completed_module_ids = {
        e.module_id
        for e in enrollments
        if e.status == "completed" or bool(e.completed_at) or bool(e.passed)
    }
    recommended = ELearningModule.query.filter(
        ELearningModule.is_active == True,
        ELearningModule.id.notin_(completed_module_ids)
    ).limit(3).all()
    
    return render_template(
        "e_learning/dashboard.html",
        profile=profile,
        enrollments=enrollments,
        certificates=certificates,
        recommended=recommended,
        page_title=tr("my_learning_dashboard"),
    )
