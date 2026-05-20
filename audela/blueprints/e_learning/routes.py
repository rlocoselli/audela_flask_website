"""E-Learning UI Routes."""

from flask import render_template, redirect, url_for, request, session, flash, Response
from flask_login import login_required, current_user
from sqlalchemy import desc
from datetime import datetime

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
    ELearningStudentFile,
    ELearningQuiz,
    UserQuizAttempt,
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
    subject_code = (module.subject.code or "").lower() if module.subject else ""
    show_exercises = subject_code == "sql" or ("python" in subject_code) or subject_code.startswith("django-")
    if show_exercises:
        exercises = ELearningExercise.query.filter_by(lesson_id=lesson_id, is_active=True).order_by(ELearningExercise.order).all()
    else:
        exercises = []
    quizzes = ELearningQuiz.query.filter_by(lesson_id=lesson_id, is_active=True).order_by(ELearningQuiz.order).all()
    
    # Get enrollment
    enrollment = UserELearningEnrollment.query.filter_by(
        user_id=current_user.id, module_id=module.id
    ).first_or_404()
    
    return render_template(
        "e_learning/lesson_view.html",
        lesson=lesson,
        module=module,
        exercises=exercises,
        show_exercises=show_exercises,
        quizzes=quizzes,
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
    subject_code = (module.subject.code or "").lower() if module.subject else ""
    is_lab_subject = subject_code == "sql" or ("python" in subject_code) or subject_code.startswith("django-")

    if not is_lab_subject:
        flash(tr("Labs are available for SQL and Python tracks only."), "info")
        return redirect(url_for("e_learning.lesson_view", lesson_id=lesson.id))
    
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
    """View and share certificate by numeric ID (legacy)."""
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


@bp.route("/certificate/share/<uuid>", methods=["GET"])
def certificate_view_uuid(uuid):
    """View and share certificate by UUID (LinkedIn-friendly share link)."""
    cert = ELearningCertificate.query.filter_by(shared_link_uuid=uuid).first()
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


@bp.route("/brain-trainer", methods=["GET"])
@login_required
def brain_trainer():
    """Interactive brain training course with mini games and progress graph."""
    return render_template(
        "e_learning/brain_trainer.html",
        page_title=tr("Brain Trainer"),
    )


@bp.route("/my-files", methods=["GET"])
@login_required
def my_files():
    """Files shared with the current student by an admin."""
    files = (
        ELearningStudentFile.query
        .filter_by(user_id=current_user.id, is_active=True)
        .order_by(ELearningStudentFile.created_at.desc())
        .all()
    )
    lang = get_user_language()
    return render_template(
        "e_learning/my_files.html",
        files=files,
        lang=lang,
        page_title=tr("my_shared_files"),
    )


# ──────────────────────────────────────────────────────────────
# Quiz routes (student-facing)
# ──────────────────────────────────────────────────────────────

@bp.route("/quiz/<int:quiz_id>", methods=["GET"])
@login_required
def quiz_detail(quiz_id):
    """Show quiz info and start button."""
    quiz = ELearningQuiz.query.filter_by(id=quiz_id, is_active=True).first_or_404()
    lang = get_user_language()
    attempts = UserQuizAttempt.query.filter_by(user_id=current_user.id, quiz_id=quiz_id).order_by(UserQuizAttempt.started_at.desc()).all()
    best = max((a for a in attempts if a.score_pct is not None), key=lambda a: a.score_pct, default=None)
    already_passed = any(a.passed for a in attempts)
    max_reached = quiz.max_attempts and len(attempts) >= quiz.max_attempts
    return render_template(
        "e_learning/quiz_detail.html",
        quiz=quiz,
        lang=lang,
        attempts=attempts,
        best=best,
        already_passed=already_passed,
        max_reached=max_reached,
        page_title=tr("quiz"),
    )


@bp.route("/quiz/<int:quiz_id>/take", methods=["GET", "POST"])
@login_required
def quiz_take(quiz_id):
    """Render quiz form (GET) or grade submission (POST)."""
    quiz = ELearningQuiz.query.filter_by(id=quiz_id, is_active=True).first_or_404()
    lang = get_user_language()

    # Guard: max attempts
    if quiz.max_attempts:
        count = UserQuizAttempt.query.filter_by(user_id=current_user.id, quiz_id=quiz_id).count()
        if count >= quiz.max_attempts:
            flash(tr("Max attempts reached"), "warning")
            return redirect(url_for("e_learning.quiz_detail", quiz_id=quiz_id))

    questions = [q for q in quiz.questions if q.is_active]
    if quiz.shuffle_questions:
        import random
        questions = random.sample(questions, len(questions))

    if request.method == "POST":
        answers = {}
        for q in questions:
            if q.question_type == "multiple_choice":
                # May be multiple checkboxes selected
                answers[str(q.id)] = request.form.getlist(f"q_{q.id}")
            elif q.question_type == "true_false":
                answers[str(q.id)] = request.form.get(f"q_{q.id}", "")
            else:  # short_answer
                answers[str(q.id)] = (request.form.get(f"q_{q.id}") or "").strip()

        # Grade with optional per-question partial credit and negative marking
        total_points = sum(q.points for q in questions)
        earned = 0.0
        question_results = {}
        question_scores = {}
        for q in questions:
            ans = answers.get(str(q.id))
            correct, question_earned = _score_quiz_question(q, ans)

            # Apply negative marking only when a wrong answer was actually submitted
            has_answer = bool(ans) if not isinstance(ans, list) else bool(set(ans))
            if has_answer and (not correct) and (q.penalty_points or 0) > 0:
                question_earned -= float(q.penalty_points or 0)

            earned += question_earned
            question_results[str(q.id)] = correct
            question_scores[str(q.id)] = {
                "earned": round(question_earned, 2),
                "max": q.points,
                "correct": bool(correct),
            }

        earned_non_negative = max(earned, 0.0)
        score_pct = round(earned_non_negative / total_points * 100) if total_points else 0
        passed = score_pct >= quiz.pass_threshold
        points_earned = quiz.points_on_pass if passed else 0

        attempt = UserQuizAttempt(
            user_id=current_user.id,
            quiz_id=quiz_id,
            submitted_at=datetime.utcnow(),
            score_pct=score_pct,
            points_earned=points_earned,
            passed=passed,
            answers_json=answers,
            question_scores_json=question_scores,
        )
        db.session.add(attempt)

        if passed:
            # Award points to profile
            profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
            if profile:
                profile.total_points = (profile.total_points or 0) + points_earned
                profile.updated_at = datetime.utcnow()

        db.session.commit()

        return render_template(
            "e_learning/quiz_results.html",
            quiz=quiz,
            lang=lang,
            attempt=attempt,
            questions=questions,
            answers=answers,
            question_results=question_results,
            question_scores=question_scores,
            score_pct=score_pct,
            passed=passed,
            page_title=tr("Quiz Results"),
        )

    return render_template(
        "e_learning/quiz_take.html",
        quiz=quiz,
        lang=lang,
        questions=questions,
        page_title=tr("quiz"),
    )


def _score_quiz_question(question, answer) -> tuple[bool, float]:
    """Return (is_fully_correct, earned_points_before_penalty)."""
    if question.question_type == "multiple_choice":
        correct_ids = {str(o.id) for o in question.options if o.is_correct}
        given_ids = set(answer) if isinstance(answer, list) else set()
        if given_ids == correct_ids:
            return True, float(question.points)
        if question.allow_partial_credit and correct_ids:
            true_positive = len(given_ids & correct_ids)
            false_positive = len(given_ids - correct_ids)
            ratio = (true_positive / len(correct_ids)) - (false_positive / len(correct_ids))
            ratio = min(max(ratio, 0.0), 1.0)
            return False, float(question.points) * ratio
        return False, 0.0

    if question.question_type == "true_false":
        correct_opt = next((o for o in question.options if o.is_correct), None)
        is_correct = bool(correct_opt and answer and str(correct_opt.id) == str(answer))
        return is_correct, float(question.points) if is_correct else 0.0

    # short_answer
    expected_raw = (question.expected_answer or "").strip().lower()
    given = (answer or "").strip().lower()
    if not expected_raw or not given:
        return False, 0.0

    keywords = [k.strip() for k in expected_raw.split(",") if k.strip()]
    if not keywords:
        is_correct = expected_raw in given
        return is_correct, float(question.points) if is_correct else 0.0

    matched = sum(1 for keyword in keywords if keyword in given)
    if matched == len(keywords):
        return True, float(question.points)
    if question.allow_partial_credit:
        ratio = matched / len(keywords)
        return False, float(question.points) * ratio
    return False, 0.0


# ──────────────────────────────────────────────────────────────────────────────
# QR code for certificate verification (public)
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/certificate/verify/<code>/qr.png", methods=["GET"])
def certificate_qr(code):
    """Return a QR-code PNG encoding the public verification URL for a certificate."""
    import qrcode
    import io

    verify_url = url_for("e_learning.verify_certificate", code=code, _external=True)
    img = qrcode.make(verify_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")
