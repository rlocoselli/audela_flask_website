"""E-Learning Admin Routes.

All routes are prefixed /e-learning/admin/ and require platform_admin role.
Provides full CRUD for subjects, modules, lessons, exercises and student files,
plus AI-powered generation / improvement / translation of content.
"""

from __future__ import annotations

import json
import os
import re
import uuid
import csv
import io
from functools import wraps
from datetime import datetime

from flask import (
    current_app,
    flash,
    jsonify,
    Response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ...extensions import db
from ...models.core import User
from ...models.e_learning import (
    ELearningExercise,
    ELearningLesson,
    ELearningModule,
    ELearningQuiz,
    ELearningQuizOption,
    ELearningQuizQuestion,
    ELearningStudentFile,
    ELearningSubject,
    UserQuizAttempt,
    UserELearningEnrollment,
)
from ...services import e_learning_ai_service as ai_svc
from ...services.ai_runtime_config import resolve_ai_runtime_config
from ...services.certificate_template_service import (
    certificate_template_dir,
    is_allowed_certificate_template_file,
    load_certificate_template_meta,
    save_certificate_template_meta,
)
from ...i18n import tr
from . import bp

# ──────────────────────────────────────────────────────────────────────────────
# Auth guard
# ──────────────────────────────────────────────────────────────────────────────

def _admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not (current_user.has_role("platform_admin") or current_user.has_role("admin")):
            flash("Acesso negado.", "danger")
            return redirect(url_for("e_learning.subjects_list"))
        return f(*args, **kwargs)
    return decorated


def _ai_enabled() -> bool:
    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    return bool(runtime.get("api_key"))


# ──────────────────────────────────────────────────────────────────────────────
# Admin dashboard
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/admin/", methods=["GET"])
@_admin_required
def admin_dashboard():
    subjects = ELearningSubject.query.order_by(ELearningSubject.order).all()
    modules = ELearningModule.query.order_by(ELearningModule.subject_id, ELearningModule.order).all()
    lessons = ELearningLesson.query.order_by(ELearningLesson.module_id, ELearningLesson.order).all()
    exercises = ELearningExercise.query.order_by(ELearningExercise.lesson_id, ELearningExercise.order).all()

    total_students = (
        db.session.query(db.func.count(db.func.distinct(UserELearningEnrollment.user_id))).scalar() or 0
    )
    files = ELearningStudentFile.query.filter_by(is_active=True).count()
    quiz_count = ELearningQuiz.query.filter_by(is_active=True).count()
    total_attempts = UserQuizAttempt.query.count()
    passed_attempts = UserQuizAttempt.query.filter_by(passed=True).count()
    attempted_students = db.session.query(db.func.count(db.func.distinct(UserQuizAttempt.user_id))).scalar() or 0
    avg_score = db.session.query(db.func.avg(UserQuizAttempt.score_pct)).filter(UserQuizAttempt.score_pct.isnot(None)).scalar() or 0

    attempt_rate = (attempted_students / total_students * 100.0) if total_students else 0.0
    pass_rate = (passed_attempts / total_attempts * 100.0) if total_attempts else 0.0

    return render_template(
        "e_learning/admin/dashboard.html",
        subjects=subjects,
        modules=modules,
        lessons=lessons,
        exercises=exercises,
        total_students=total_students,
        total_files=files,
        total_quizzes=quiz_count,
        quiz_attempt_rate=round(attempt_rate, 1),
        quiz_pass_rate=round(pass_rate, 1),
        quiz_avg_score=round(float(avg_score or 0), 1),
        ai_enabled=_ai_enabled(),
        all_langs=ai_svc.ALL_LANGS,
        lang_names=ai_svc.LANG_NAMES,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Subject CRUD
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/admin/subjects/new", methods=["GET", "POST"])
@bp.route("/admin/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@_admin_required
def admin_subject_form(subject_id: int | None = None):
    subject = ELearningSubject.query.get_or_404(subject_id) if subject_id else None

    if request.method == "POST":
        code = request.form.get("code", "").strip().lower()
        if not code:
            flash("Code is required.", "danger")
            return redirect(request.url)

        name_i18n = _collect_i18n("name")
        desc_i18n = _collect_i18n("description")
        icon_url = request.form.get("icon_url", "").strip() or None
        order = int(request.form.get("order", 0) or 0)
        is_active = request.form.get("is_active") == "1"

        if subject is None:
            if ELearningSubject.query.filter_by(code=code).first():
                flash(f"Subject code '{code}' already exists.", "danger")
                return redirect(request.url)
            subject = ELearningSubject(code=code)
            db.session.add(subject)

        subject.code = code
        subject.name_i18n = name_i18n
        subject.description_i18n = desc_i18n
        subject.icon_url = icon_url
        subject.order = order
        subject.is_active = is_active
        db.session.commit()
        flash("Subject saved.", "success")
        return redirect(url_for("e_learning.admin_dashboard"))

    return render_template(
        "e_learning/admin/subject_form.html",
        subject=subject,
        all_langs=ai_svc.ALL_LANGS,
        lang_names=ai_svc.LANG_NAMES,
        ai_enabled=_ai_enabled(),
    )


@bp.route("/admin/subjects/<int:subject_id>/delete", methods=["POST"])
@_admin_required
def admin_subject_delete(subject_id: int):
    subject = ELearningSubject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash("Subject deleted.", "success")
    return redirect(url_for("e_learning.admin_dashboard"))


# ──────────────────────────────────────────────────────────────────────────────
# Module CRUD
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/admin/modules/new", methods=["GET", "POST"])
@bp.route("/admin/modules/<int:module_id>/edit", methods=["GET", "POST"])
@_admin_required
def admin_module_form(module_id: int | None = None):
    module = ELearningModule.query.get_or_404(module_id) if module_id else None
    subjects = ELearningSubject.query.order_by(ELearningSubject.order).all()

    if request.method == "POST":
        subject_id = int(request.form.get("subject_id", 0) or 0)
        code = request.form.get("code", "").strip().lower()
        if not code or not subject_id:
            flash("Subject and code are required.", "danger")
            return redirect(request.url)

        title_i18n = _collect_i18n("title")
        desc_i18n = _collect_i18n("description")
        level = request.form.get("level", "beginner")
        order = int(request.form.get("order", 0) or 0)
        estimated_hours = float(request.form.get("estimated_hours", 2.0) or 2.0)
        pass_threshold = int(request.form.get("pass_threshold", 80) or 80)
        points_on_completion = int(request.form.get("points_on_completion", 100) or 100)
        sample_database_schema = request.form.get("sample_database_schema", "").strip() or None
        sample_data_sql = request.form.get("sample_data_sql", "").strip() or None
        is_active = request.form.get("is_active") == "1"

        if module is None:
            if ELearningModule.query.filter_by(subject_id=subject_id, code=code).first():
                flash(f"Module code '{code}' already exists in this subject.", "danger")
                return redirect(request.url)
            module = ELearningModule(subject_id=subject_id, code=code)
            db.session.add(module)

        module.subject_id = subject_id
        module.code = code
        module.title_i18n = title_i18n
        module.description_i18n = desc_i18n
        module.level = level
        module.order = order
        module.estimated_hours = estimated_hours
        module.pass_threshold = pass_threshold
        module.points_on_completion = points_on_completion
        module.sample_database_schema = sample_database_schema
        module.sample_data_sql = sample_data_sql
        module.is_active = is_active
        db.session.commit()
        flash("Module saved.", "success")
        return redirect(url_for("e_learning.admin_dashboard"))

    return render_template(
        "e_learning/admin/module_form.html",
        module=module,
        subjects=subjects,
        all_langs=ai_svc.ALL_LANGS,
        lang_names=ai_svc.LANG_NAMES,
        ai_enabled=_ai_enabled(),
    )


@bp.route("/admin/modules/<int:module_id>/delete", methods=["POST"])
@_admin_required
def admin_module_delete(module_id: int):
    module = ELearningModule.query.get_or_404(module_id)
    db.session.delete(module)
    db.session.commit()
    flash("Module deleted.", "success")
    return redirect(url_for("e_learning.admin_dashboard"))


# ──────────────────────────────────────────────────────────────────────────────
# Lesson CRUD
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/admin/lessons/new", methods=["GET", "POST"])
@bp.route("/admin/lessons/<int:lesson_id>/edit", methods=["GET", "POST"])
@_admin_required
def admin_lesson_form(lesson_id: int | None = None):
    lesson = ELearningLesson.query.get_or_404(lesson_id) if lesson_id else None
    modules = ELearningModule.query.order_by(ELearningModule.subject_id, ELearningModule.order).all()

    if request.method == "POST":
        module_id = int(request.form.get("module_id", 0) or 0)
        code = request.form.get("code", "").strip().lower()
        if not code or not module_id:
            flash("Module and code are required.", "danger")
            return redirect(request.url)

        title_i18n = _collect_i18n("title")
        desc_i18n = _collect_i18n("description")
        content_html_i18n = _collect_i18n("content_html")
        key_concepts_raw = request.form.get("key_concepts_json", "").strip()
        example_sql_i18n = _collect_i18n("example_sql")
        order = int(request.form.get("order", 0) or 0)
        is_active = request.form.get("is_active") == "1"

        try:
            key_concepts_i18n = json.loads(key_concepts_raw) if key_concepts_raw else {}
        except json.JSONDecodeError:
            key_concepts_i18n = {}

        if lesson is None:
            if ELearningLesson.query.filter_by(module_id=module_id, code=code).first():
                flash(f"Lesson code '{code}' already exists in this module.", "danger")
                return redirect(request.url)
            lesson = ELearningLesson(module_id=module_id, code=code)
            db.session.add(lesson)

        lesson.module_id = module_id
        lesson.code = code
        lesson.title_i18n = title_i18n
        lesson.description_i18n = desc_i18n
        lesson.content_html_i18n = content_html_i18n
        lesson.key_concepts_i18n = key_concepts_i18n
        lesson.example_sql_i18n = example_sql_i18n
        lesson.order = order
        lesson.is_active = is_active
        db.session.commit()
        flash("Lesson saved.", "success")
        return redirect(url_for("e_learning.admin_dashboard"))

    return render_template(
        "e_learning/admin/lesson_form.html",
        lesson=lesson,
        modules=modules,
        all_langs=ai_svc.ALL_LANGS,
        lang_names=ai_svc.LANG_NAMES,
        ai_enabled=_ai_enabled(),
    )


@bp.route("/admin/lessons/<int:lesson_id>/delete", methods=["POST"])
@_admin_required
def admin_lesson_delete(lesson_id: int):
    lesson = ELearningLesson.query.get_or_404(lesson_id)
    db.session.delete(lesson)
    db.session.commit()
    flash("Lesson deleted.", "success")
    return redirect(url_for("e_learning.admin_dashboard"))


# ──────────────────────────────────────────────────────────────────────────────
# Exercise CRUD
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/admin/exercises/new", methods=["GET", "POST"])
@bp.route("/admin/exercises/<int:exercise_id>/edit", methods=["GET", "POST"])
@_admin_required
def admin_exercise_form(exercise_id: int | None = None):
    exercise = ELearningExercise.query.get_or_404(exercise_id) if exercise_id else None
    lessons = (
        ELearningLesson.query
        .join(ELearningModule)
        .order_by(ELearningModule.subject_id, ELearningModule.order, ELearningLesson.order)
        .all()
    )

    if request.method == "POST":
        lesson_id = int(request.form.get("lesson_id", 0) or 0)
        code = request.form.get("code", "").strip().lower()
        if not code or not lesson_id:
            flash("Lesson and code are required.", "danger")
            return redirect(request.url)

        ex_type = request.form.get("type", "sql_query")
        title_i18n = _collect_i18n("title")
        instr_i18n = _collect_i18n("instruction")
        hint_i18n = _collect_i18n("hint")
        expected_sql = request.form.get("expected_sql", "").strip() or None
        dml_operation = request.form.get("dml_operation", "").strip() or None
        validation_query = request.form.get("validation_query", "").strip() or None
        passing_condition = request.form.get("passing_condition", "").strip() or None
        expected_result_raw = request.form.get("expected_result_json", "").strip()
        try:
            import json as _json
            expected_result_json = _json.loads(expected_result_raw) if expected_result_raw else None
        except ValueError:
            flash("Expected result JSON is not valid JSON.", "danger")
            return redirect(request.url)
        points = int(request.form.get("points", 10) or 10)
        order = int(request.form.get("order", 0) or 0)
        is_active = request.form.get("is_active") == "1"

        if exercise is None:
            if ELearningExercise.query.filter_by(lesson_id=lesson_id, code=code).first():
                flash(f"Exercise code '{code}' already exists in this lesson.", "danger")
                return redirect(request.url)
            exercise = ELearningExercise(lesson_id=lesson_id, code=code)
            db.session.add(exercise)

        exercise.lesson_id = lesson_id
        exercise.code = code
        exercise.type = ex_type
        exercise.title_i18n = title_i18n
        exercise.instruction_i18n = instr_i18n
        exercise.hint_i18n = hint_i18n
        exercise.expected_sql = expected_sql
        exercise.expected_result_json = expected_result_json
        exercise.dml_operation = dml_operation
        exercise.validation_query = validation_query
        exercise.passing_condition = passing_condition
        exercise.points = points
        exercise.order = order
        exercise.is_active = is_active
        db.session.commit()
        flash("Exercise saved.", "success")
        return redirect(url_for("e_learning.admin_dashboard"))

    return render_template(
        "e_learning/admin/exercise_form.html",
        exercise=exercise,
        lessons=lessons,
        all_langs=ai_svc.ALL_LANGS,
        lang_names=ai_svc.LANG_NAMES,
        ai_enabled=_ai_enabled(),
    )


@bp.route("/admin/exercises/<int:exercise_id>/delete", methods=["POST"])
@_admin_required
def admin_exercise_delete(exercise_id: int):
    exercise = ELearningExercise.query.get_or_404(exercise_id)
    db.session.delete(exercise)
    db.session.commit()
    flash("Exercise deleted.", "success")
    return redirect(url_for("e_learning.admin_dashboard"))


# ──────────────────────────────────────────────────────────────────────────────
# Student file management
# ──────────────────────────────────────────────────────────────────────────────

def _upload_dir() -> str:
    base = os.path.join(current_app.instance_path, "student_files")
    os.makedirs(base, exist_ok=True)
    return base


ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "md",
    "png", "jpg", "jpeg", "gif", "svg", "zip", "pptx", "ppt",
}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route("/admin/student-files", methods=["GET"])
@_admin_required
def admin_student_files():
    students = (
        User.query
        .join(User.student_files)
        .group_by(User.id)
        .all()
    )
    # fallback: all users for the dropdown
    all_users = User.query.order_by(User.email).all()
    files = ELearningStudentFile.query.order_by(ELearningStudentFile.created_at.desc()).all()
    modules = ELearningModule.query.order_by(ELearningModule.order).all()
    lessons = ELearningLesson.query.order_by(ELearningLesson.order).all()

    return render_template(
        "e_learning/admin/student_files.html",
        files=files,
        all_users=all_users,
        modules=modules,
        lessons=lessons,
    )


@bp.route("/admin/student-files/upload", methods=["POST"])
@_admin_required
def admin_student_file_upload():
    user_id = int(request.form.get("user_id", 0) or 0)
    if not user_id or not User.query.get(user_id):
        flash("Valid student is required.", "danger")
        return redirect(url_for("e_learning.admin_student_files"))

    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("e_learning.admin_student_files"))

    if not _allowed_file(file.filename):
        flash("File type not allowed.", "danger")
        return redirect(url_for("e_learning.admin_student_files"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = _upload_dir()
    dest = os.path.join(upload_dir, safe_name)
    file.save(dest)

    label = request.form.get("label", "").strip() or None
    description = request.form.get("description", "").strip() or None
    module_id_raw = request.form.get("module_id", "").strip()
    lesson_id_raw = request.form.get("lesson_id", "").strip()

    sf = ELearningStudentFile(
        user_id=user_id,
        module_id=int(module_id_raw) if module_id_raw else None,
        lesson_id=int(lesson_id_raw) if lesson_id_raw else None,
        uploaded_by_user_id=current_user.id,
        original_filename=secure_filename(file.filename),
        storage_path=safe_name,
        mime_type=file.mimetype or None,
        size_bytes=os.path.getsize(dest),
        label=label or secure_filename(file.filename),
        description=description,
    )
    db.session.add(sf)
    db.session.commit()
    flash("File uploaded successfully.", "success")
    return redirect(url_for("e_learning.admin_student_files"))


@bp.route("/admin/student-files/<int:file_id>/delete", methods=["POST"])
@_admin_required
def admin_student_file_delete(file_id: int):
    sf = ELearningStudentFile.query.get_or_404(file_id)
    # Remove physical file
    try:
        path = os.path.join(_upload_dir(), sf.storage_path)
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
    db.session.delete(sf)
    db.session.commit()
    flash("File deleted.", "success")
    return redirect(url_for("e_learning.admin_student_files"))


# ──────────────────────────────────────────────────────────────────────────────
# Certificate template management
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/admin/certificate-template", methods=["GET"])
@_admin_required
def admin_certificate_template():
    meta = load_certificate_template_meta(current_app)
    return render_template(
        "e_learning/admin/certificate_template.html",
        template_meta=meta,
        has_background=bool(meta.get("background_image")),
    )


@bp.route("/admin/certificate-template/upload", methods=["POST"])
@_admin_required
def admin_certificate_template_upload():
    template_name = (request.form.get("template_name") or "").strip() or "Default Certificate"
    uploaded = request.files.get("template_file")

    if not uploaded or not uploaded.filename:
        flash("Please choose an image file.", "danger")
        return redirect(url_for("e_learning.admin_certificate_template"))

    if not is_allowed_certificate_template_file(uploaded.filename):
        flash("Unsupported format. Allowed: PNG, JPG, JPEG, WEBP.", "danger")
        return redirect(url_for("e_learning.admin_certificate_template"))

    ext = uploaded.filename.rsplit(".", 1)[1].lower()
    safe_name = f"certificate_template_{uuid.uuid4().hex}.{ext}"

    storage_dir = certificate_template_dir(current_app)
    meta = load_certificate_template_meta(current_app)
    old_image = meta.get("background_image")

    target = os.path.join(storage_dir, safe_name)
    uploaded.save(target)

    if old_image:
        old_path = os.path.join(storage_dir, old_image)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    save_certificate_template_meta(
        current_app,
        {
            "template_name": template_name,
            "background_image": safe_name,
            "updated_by": current_user.email,
        },
    )
    flash("Certificate template updated.", "success")
    return redirect(url_for("e_learning.admin_certificate_template"))


@bp.route("/admin/certificate-template/reset", methods=["POST"])
@_admin_required
def admin_certificate_template_reset():
    meta = load_certificate_template_meta(current_app)
    storage_dir = certificate_template_dir(current_app)
    old_image = meta.get("background_image")
    if old_image:
        old_path = os.path.join(storage_dir, old_image)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    save_certificate_template_meta(
        current_app,
        {
            "template_name": "Default Certificate",
            "background_image": None,
            "updated_by": current_user.email,
        },
    )
    flash("Certificate template reset to default.", "success")
    return redirect(url_for("e_learning.admin_certificate_template"))


# Student-facing download
@bp.route("/my-files/<int:file_id>/download", methods=["GET"])
@login_required
def student_file_download(file_id: int):
    sf = ELearningStudentFile.query.get_or_404(file_id)
    if sf.user_id != current_user.id and not (
        current_user.has_role("platform_admin") or current_user.has_role("admin")
    ):
        flash("Access denied.", "danger")
        return redirect(url_for("e_learning.subjects_list"))
    return send_from_directory(
        _upload_dir(),
        sf.storage_path,
        as_attachment=True,
        download_name=sf.original_filename,
    )


# ──────────────────────────────────────────────────────────────────────────────
# AI API endpoints (JSON)
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/admin/api/ai/generate", methods=["POST"])
@_admin_required
def admin_api_ai_generate():
    """Generate content from a prompt."""
    data = request.json or {}
    prompt = (data.get("prompt") or "").strip()
    field = data.get("field", "content")
    lang = data.get("lang", "en")
    context = data.get("context", "")

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    result = ai_svc.generate_content(prompt=prompt, field=field, lang=lang, context=context)
    if not result:
        return jsonify({"error": "AI unavailable or no result returned"}), 503

    return jsonify({"result": result})


@bp.route("/admin/api/ai/improve", methods=["POST"])
@_admin_required
def admin_api_ai_improve():
    """Improve / fix existing text."""
    data = request.json or {}
    text = (data.get("text") or "").strip()
    field = data.get("field", "content")
    lang = data.get("lang", "en")

    if not text:
        return jsonify({"error": "text is required"}), 400

    result = ai_svc.improve_text(text=text, field=field, lang=lang)
    return jsonify({"result": result})


@bp.route("/admin/api/ai/translate", methods=["POST"])
@_admin_required
def admin_api_ai_translate():
    """Translate text into all (or specified) languages."""
    data = request.json or {}
    text = (data.get("text") or "").strip()
    source_lang = data.get("source_lang", "en")
    target_langs = data.get("target_langs") or None  # None → all

    if not text:
        return jsonify({"error": "text is required"}), 400

    translations = ai_svc.translate_content(
        text=text, source_lang=source_lang, target_langs=target_langs
    )
    return jsonify({"translations": translations})


@bp.route("/admin/api/ai/translate-all-fields", methods=["POST"])
@_admin_required
def admin_api_ai_translate_all_fields():
    """Given a dict of {lang: text}, fill missing lang gaps for all fields.

    Body: { "fields": { "title": {"en": "Introduction to SELECT"}, ... }, "source_lang": "en" }
    Returns: { "fields": { "title": {"en": "...", "pt": "...", ...}, ... } }
    """
    data = request.json or {}
    fields: dict = data.get("fields", {})
    source_lang = data.get("source_lang", "en")

    result = {}
    for field_name, i18n_dict in fields.items():
        result[field_name] = ai_svc.translate_i18n_dict(i18n_dict, source_lang=source_lang)

    return jsonify({"fields": result})


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _quiz_to_payload(quiz: ELearningQuiz) -> dict:
    return {
        "code": quiz.code,
        "order": quiz.order,
        "title_i18n": quiz.title_i18n or {},
        "description_i18n": quiz.description_i18n or {},
        "time_limit_minutes": quiz.time_limit_minutes,
        "pass_threshold": quiz.pass_threshold,
        "max_attempts": quiz.max_attempts,
        "shuffle_questions": bool(quiz.shuffle_questions),
        "show_correct_answers": bool(quiz.show_correct_answers),
        "points_on_pass": quiz.points_on_pass,
        "is_active": bool(quiz.is_active),
        "questions": [
            {
                "order": q.order,
                "question_type": q.question_type,
                "text_i18n": q.text_i18n or {},
                "explanation_i18n": q.explanation_i18n or {},
                "points": q.points,
                "allow_partial_credit": bool(q.allow_partial_credit),
                "penalty_points": q.penalty_points,
                "expected_answer": q.expected_answer,
                "is_active": bool(q.is_active),
                "options": [
                    {
                        "order": o.order,
                        "text_i18n": o.text_i18n or {},
                        "is_correct": bool(o.is_correct),
                    }
                    for o in q.options
                ],
            }
            for q in quiz.questions
        ],
    }


def _create_quiz_from_payload(payload: dict, lesson_id: int) -> ELearningQuiz:
    code = (payload.get("code") or f"quiz-{uuid.uuid4().hex[:8]}").strip().lower()
    if ELearningQuiz.query.filter_by(lesson_id=lesson_id, code=code).first():
        code = f"{code}-{uuid.uuid4().hex[:4]}"

    quiz = ELearningQuiz(
        lesson_id=lesson_id,
        code=code,
        order=int(payload.get("order") or 0),
        title_i18n=payload.get("title_i18n") or {"en": code},
        description_i18n=payload.get("description_i18n") or {},
        time_limit_minutes=payload.get("time_limit_minutes"),
        pass_threshold=int(payload.get("pass_threshold") or 70),
        max_attempts=payload.get("max_attempts"),
        shuffle_questions=bool(payload.get("shuffle_questions")),
        show_correct_answers=bool(payload.get("show_correct_answers", True)),
        points_on_pass=int(payload.get("points_on_pass") or 20),
        is_active=bool(payload.get("is_active", True)),
    )
    db.session.add(quiz)
    db.session.flush()

    for q_raw in payload.get("questions", []):
        question = ELearningQuizQuestion(
            quiz_id=quiz.id,
            order=int(q_raw.get("order") or 0),
            question_type=(q_raw.get("question_type") or "multiple_choice").strip(),
            text_i18n=q_raw.get("text_i18n") or {},
            explanation_i18n=q_raw.get("explanation_i18n") or {},
            points=max(int(q_raw.get("points") or 1), 0),
            allow_partial_credit=bool(q_raw.get("allow_partial_credit", False)),
            penalty_points=max(int(q_raw.get("penalty_points") or 0), 0),
            expected_answer=(q_raw.get("expected_answer") or "").strip() or None,
            is_active=bool(q_raw.get("is_active", True)),
        )
        if question.penalty_points > question.points:
            question.penalty_points = question.points
        db.session.add(question)
        db.session.flush()

        for o_raw in q_raw.get("options", []):
            option = ELearningQuizOption(
                question_id=question.id,
                order=int(o_raw.get("order") or 0),
                text_i18n=o_raw.get("text_i18n") or {},
                is_correct=bool(o_raw.get("is_correct")),
            )
            db.session.add(option)

    return quiz

def _collect_i18n(prefix: str) -> dict:
    """Gather form fields named ``{prefix}__{lang}`` into a dict."""
    result = {}
    for lang in ai_svc.ALL_LANGS:
        value = (request.form.get(f"{prefix}__{lang}") or "").strip()
        if value:
            result[lang] = value
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Quiz admin CRUD
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/admin/quizzes", methods=["GET"])
@_admin_required
def admin_quiz_list():
    quizzes = ELearningQuiz.query.order_by(ELearningQuiz.lesson_id, ELearningQuiz.order).all()
    lessons = ELearningLesson.query.order_by(ELearningLesson.module_id, ELearningLesson.order).all()
    analytics = {}
    for quiz in quizzes:
        attempts_q = UserQuizAttempt.query.filter_by(quiz_id=quiz.id)
        attempt_count = attempts_q.count()
        passed_count = attempts_q.filter_by(passed=True).count()
        avg_score = attempts_q.with_entities(db.func.avg(UserQuizAttempt.score_pct)).filter(UserQuizAttempt.score_pct.isnot(None)).scalar() or 0
        analytics[quiz.id] = {
            "attempts": attempt_count,
            "pass_rate": round((passed_count / attempt_count * 100.0), 1) if attempt_count else 0.0,
            "avg_score": round(float(avg_score or 0), 1),
        }
    return render_template("e_learning/admin/quiz_list.html", quizzes=quizzes, lessons=lessons, analytics=analytics)


@bp.route("/admin/quizzes/new", methods=["GET", "POST"])
@bp.route("/admin/quizzes/<int:quiz_id>/edit", methods=["GET", "POST"])
@_admin_required
def admin_quiz_form(quiz_id=None):
    quiz = ELearningQuiz.query.get_or_404(quiz_id) if quiz_id else None
    lessons = ELearningLesson.query.order_by(ELearningLesson.module_id, ELearningLesson.order).all()

    if request.method == "POST":
        lesson_id = request.form.get("lesson_id", type=int)
        code = (request.form.get("code") or "").strip()
        if not lesson_id or not code:
            flash("Lesson and code are required.", "danger")
            return render_template(
                "e_learning/admin/quiz_form.html",
                quiz=quiz,
                lessons=lessons,
                all_langs=ai_svc.ALL_LANGS,
                lang_names=ai_svc.LANG_NAMES,
                ai_enabled=_ai_enabled(),
            )

        if not quiz:
            quiz = ELearningQuiz(lesson_id=lesson_id, code=code)
            db.session.add(quiz)
        else:
            quiz.lesson_id = lesson_id
            quiz.code = code

        quiz.order = request.form.get("order", 0, type=int)
        quiz.title_i18n = _collect_i18n("title")
        quiz.description_i18n = _collect_i18n("description")
        quiz.time_limit_minutes = request.form.get("time_limit_minutes", type=int) or None
        quiz.pass_threshold = request.form.get("pass_threshold", 70, type=int)
        quiz.max_attempts = request.form.get("max_attempts", type=int) or None
        quiz.shuffle_questions = bool(request.form.get("shuffle_questions"))
        quiz.show_correct_answers = bool(request.form.get("show_correct_answers"))
        quiz.points_on_pass = request.form.get("points_on_pass", 20, type=int)
        quiz.is_active = bool(request.form.get("is_active"))
        quiz.updated_at = datetime.utcnow()

        db.session.commit()
        flash("Quiz saved.", "success")
        return redirect(url_for("e_learning.admin_quiz_form", quiz_id=quiz.id))

    return render_template(
        "e_learning/admin/quiz_form.html",
        quiz=quiz,
        lessons=lessons,
        all_langs=ai_svc.ALL_LANGS,
        lang_names=ai_svc.LANG_NAMES,
        ai_enabled=_ai_enabled(),
    )


@bp.route("/admin/quizzes/<int:quiz_id>/delete", methods=["POST"])
@_admin_required
def admin_quiz_delete(quiz_id):
    quiz = ELearningQuiz.query.get_or_404(quiz_id)
    db.session.delete(quiz)
    db.session.commit()
    flash("Quiz deleted.", "success")
    return redirect(url_for("e_learning.admin_quiz_list"))


@bp.route("/admin/quizzes/<int:quiz_id>/export.json", methods=["GET"])
@_admin_required
def admin_quiz_export_json(quiz_id: int):
    quiz = ELearningQuiz.query.get_or_404(quiz_id)
    payload = _quiz_to_payload(quiz)
    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"{quiz.code}_quiz.json"
    return Response(
        json_bytes,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/admin/quizzes/<int:quiz_id>/export.csv", methods=["GET"])
@_admin_required
def admin_quiz_export_csv(quiz_id: int):
    quiz = ELearningQuiz.query.get_or_404(quiz_id)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "quiz_code",
        "lesson_id",
        "question_order",
        "question_type",
        "question_points",
        "allow_partial_credit",
        "penalty_points",
        "expected_answer",
        "question_text_en",
        "question_text_pt",
        "question_text_fr",
        "question_text_es",
        "question_text_it",
        "question_text_de",
        "option_order",
        "option_is_correct",
        "option_text_en",
        "option_text_pt",
        "option_text_fr",
        "option_text_es",
        "option_text_it",
        "option_text_de",
    ])

    for q in quiz.questions:
        if q.options:
            for o in q.options:
                writer.writerow([
                    quiz.code,
                    quiz.lesson_id,
                    q.order,
                    q.question_type,
                    q.points,
                    int(bool(q.allow_partial_credit)),
                    q.penalty_points,
                    q.expected_answer or "",
                    (q.text_i18n or {}).get("en", ""),
                    (q.text_i18n or {}).get("pt", ""),
                    (q.text_i18n or {}).get("fr", ""),
                    (q.text_i18n or {}).get("es", ""),
                    (q.text_i18n or {}).get("it", ""),
                    (q.text_i18n or {}).get("de", ""),
                    o.order,
                    int(bool(o.is_correct)),
                    (o.text_i18n or {}).get("en", ""),
                    (o.text_i18n or {}).get("pt", ""),
                    (o.text_i18n or {}).get("fr", ""),
                    (o.text_i18n or {}).get("es", ""),
                    (o.text_i18n or {}).get("it", ""),
                    (o.text_i18n or {}).get("de", ""),
                ])
        else:
            writer.writerow([
                quiz.code,
                quiz.lesson_id,
                q.order,
                q.question_type,
                q.points,
                int(bool(q.allow_partial_credit)),
                q.penalty_points,
                q.expected_answer or "",
                (q.text_i18n or {}).get("en", ""),
                (q.text_i18n or {}).get("pt", ""),
                (q.text_i18n or {}).get("fr", ""),
                (q.text_i18n or {}).get("es", ""),
                (q.text_i18n or {}).get("it", ""),
                (q.text_i18n or {}).get("de", ""),
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ])

    filename = f"{quiz.code}_quiz.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/admin/quizzes/import/json", methods=["POST"])
@_admin_required
def admin_quiz_import_json():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        flash("Please choose a JSON file.", "danger")
        return redirect(url_for("e_learning.admin_quiz_list"))

    lesson_id = request.form.get("lesson_id", type=int)
    if not lesson_id:
        flash("Lesson is required for import.", "danger")
        return redirect(url_for("e_learning.admin_quiz_list"))

    try:
        data = json.loads(uploaded.read().decode("utf-8"))
    except Exception:
        flash("Invalid JSON file.", "danger")
        return redirect(url_for("e_learning.admin_quiz_list"))

    items = data if isinstance(data, list) else [data]
    imported = 0
    for item in items:
        quiz = _create_quiz_from_payload(item, lesson_id)
        imported += 1
        db.session.flush()
    db.session.commit()

    flash(f"Imported {imported} quiz(zes) from JSON.", "success")
    return redirect(url_for("e_learning.admin_quiz_list"))


@bp.route("/admin/quizzes/import/csv", methods=["POST"])
@_admin_required
def admin_quiz_import_csv():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        flash("Please choose a CSV file.", "danger")
        return redirect(url_for("e_learning.admin_quiz_list"))

    lesson_id = request.form.get("lesson_id", type=int)
    code = (request.form.get("code") or "").strip().lower()
    title_en = (request.form.get("title_en") or "").strip() or code
    if not lesson_id or not code:
        flash("Lesson and quiz code are required for CSV import.", "danger")
        return redirect(url_for("e_learning.admin_quiz_list"))

    try:
        text = uploaded.read().decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(text)))
    except Exception:
        flash("Invalid CSV file.", "danger")
        return redirect(url_for("e_learning.admin_quiz_list"))

    quiz = ELearningQuiz(
        lesson_id=lesson_id,
        code=code,
        title_i18n={"en": title_en},
        description_i18n={"en": "Imported from CSV"},
    )
    db.session.add(quiz)
    db.session.flush()

    q_by_order: dict[int, ELearningQuizQuestion] = {}
    for row in rows:
        order = int(row.get("question_order") or 0)
        q = q_by_order.get(order)
        if q is None:
            q = ELearningQuizQuestion(
                quiz_id=quiz.id,
                order=order,
                question_type=(row.get("question_type") or "multiple_choice").strip(),
                points=max(int(row.get("question_points") or 1), 0),
                allow_partial_credit=bool(int(row.get("allow_partial_credit") or 0)),
                penalty_points=max(int(row.get("penalty_points") or 0), 0),
                expected_answer=(row.get("expected_answer") or "").strip() or None,
                text_i18n={
                    "en": row.get("question_text_en") or "",
                    "pt": row.get("question_text_pt") or "",
                    "fr": row.get("question_text_fr") or "",
                    "es": row.get("question_text_es") or "",
                    "it": row.get("question_text_it") or "",
                    "de": row.get("question_text_de") or "",
                },
            )
            db.session.add(q)
            db.session.flush()
            q_by_order[order] = q

        option_text_en = (row.get("option_text_en") or "").strip()
        if option_text_en:
            opt = ELearningQuizOption(
                question_id=q.id,
                order=int(row.get("option_order") or 0),
                is_correct=bool(int(row.get("option_is_correct") or 0)),
                text_i18n={
                    "en": row.get("option_text_en") or "",
                    "pt": row.get("option_text_pt") or "",
                    "fr": row.get("option_text_fr") or "",
                    "es": row.get("option_text_es") or "",
                    "it": row.get("option_text_it") or "",
                    "de": row.get("option_text_de") or "",
                },
            )
            db.session.add(opt)

    db.session.commit()
    flash(f"Imported quiz '{quiz.code}' from CSV.", "success")
    return redirect(url_for("e_learning.admin_quiz_form", quiz_id=quiz.id))


# ── Questions ─────────────────────────────────────────────────────────────────

@bp.route("/admin/quizzes/<int:quiz_id>/questions/new", methods=["GET", "POST"])
@bp.route("/admin/questions/<int:question_id>/edit", methods=["GET", "POST"])
@_admin_required
def admin_quiz_question_form(quiz_id=None, question_id=None):
    question = ELearningQuizQuestion.query.get_or_404(question_id) if question_id else None
    if question:
        quiz = question.quiz
    else:
        quiz = ELearningQuiz.query.get_or_404(quiz_id)

    if request.method == "POST":
        if not question:
            question = ELearningQuizQuestion(quiz_id=quiz.id)
            db.session.add(question)

        question.order = request.form.get("order", 0, type=int)
        question.question_type = request.form.get("question_type", "multiple_choice")
        question.text_i18n = _collect_i18n("text")
        question.explanation_i18n = _collect_i18n("explanation")
        question.points = request.form.get("points", 1, type=int)
        question.allow_partial_credit = bool(request.form.get("allow_partial_credit"))
        question.penalty_points = max(request.form.get("penalty_points", 0, type=int), 0)
        if question.penalty_points > question.points:
            question.penalty_points = question.points
        question.expected_answer = (request.form.get("expected_answer") or "").strip() or None
        question.is_active = bool(request.form.get("is_active"))
        db.session.flush()

        # Rebuild options from POST data (option__text__{lang}_{idx} / option__is_correct_{idx})
        # Count how many option slots were submitted
        idx = 0
        new_options = []
        while True:
            text_dict = {}
            has_any = False
            for lang in ai_svc.ALL_LANGS:
                val = (request.form.get(f"option__text__{lang}_{idx}") or "").strip()
                if val:
                    text_dict[lang] = val
                    has_any = True
            if not has_any:
                break
            is_correct = bool(request.form.get(f"option__is_correct_{idx}"))
            new_options.append(ELearningQuizOption(question_id=question.id, order=idx, text_i18n=text_dict, is_correct=is_correct))
            idx += 1

        # Delete old options and replace
        ELearningQuizOption.query.filter_by(question_id=question.id).delete()
        for opt in new_options:
            db.session.add(opt)

        db.session.commit()
        flash("Question saved.", "success")
        return redirect(url_for("e_learning.admin_quiz_form", quiz_id=quiz.id))

    return render_template(
        "e_learning/admin/quiz_question_form.html",
        quiz=quiz,
        question=question,
        all_langs=ai_svc.ALL_LANGS,
        lang_names=ai_svc.LANG_NAMES,
        ai_enabled=_ai_enabled(),
    )


@bp.route("/admin/questions/<int:question_id>/delete", methods=["POST"])
@_admin_required
def admin_quiz_question_delete(question_id):
    q = ELearningQuizQuestion.query.get_or_404(question_id)
    quiz_id = q.quiz_id
    db.session.delete(q)
    db.session.commit()
    flash("Question deleted.", "success")
    return redirect(url_for("e_learning.admin_quiz_form", quiz_id=quiz_id))


# ──────────────────────────────────────────────────────────────────────────────
# Certificate template image preview (admin only – serves stored file)
# ──────────────────────────────────────────────────────────────────────────────

@bp.route("/admin/certificate-template/preview", methods=["GET"])
@_admin_required
def admin_certificate_template_preview():
    """Serve the currently active certificate background image."""
    from ...services.certificate_template_service import (
        certificate_template_dir,
        load_certificate_template_meta,
    )

    meta = load_certificate_template_meta(current_app)
    bg = meta.get("background_image")
    if not bg:
        return Response("No background set", status=404)

    storage_dir = certificate_template_dir(current_app)
    return send_from_directory(storage_dir, bg)
