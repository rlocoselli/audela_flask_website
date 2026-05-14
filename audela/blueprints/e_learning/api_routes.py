"""E-Learning API Routes - Exercise submission, scoring, achievements."""

from flask import request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from datetime import datetime
import json
import csv
import io
import zipfile
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch

from ...extensions import db
from ...models.e_learning import (
    ELearningModule,
    ELearningExercise,
    UserELearningEnrollment,
    UserELearningSubmission,
    UserELearningProfile,
    UserAchievement,
    Achievement,
    ELearningCertificate,
    ELearningSampleDatabase,
)
from ...services.e_learning_service import ELearningService
from ...services.analytics_service import track_event
from ...i18n import tr
from . import bp


service = ELearningService()


@bp.route("/api/submit-exercise", methods=["POST"])
@login_required
def api_submit_exercise():
    """Evaluate exercise submission and award points/achievements."""
    data = request.json or {}
    exercise_id = data.get("exercise_id")
    module_id = data.get("module_id")
    submitted_sql = data.get("submitted_sql")
    
    if not all([exercise_id, module_id, submitted_sql]):
        return jsonify({"error": "Missing required fields"}), 400
    
    exercise = ELearningExercise.query.get_or_404(exercise_id)
    module = ELearningModule.query.get_or_404(module_id)
    
    # Get or create enrollment
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
    
    # Execute and evaluate
    result = service.execute_and_evaluate_exercise(
        exercise=exercise,
        module=module,
        user_id=current_user.id,
        submitted_sql=submitted_sql,
        enrollment=enrollment
    )
    
    # Award points and check achievements
    if result["is_correct"]:
        profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
        if not profile:
            profile = UserELearningProfile(user_id=current_user.id)
            db.session.add(profile)
            db.session.commit()
        
        # Add points
        points_earned = exercise.points
        profile.total_points += points_earned
        profile.last_activity_at = datetime.utcnow()
        
        # Check level up (100 points per level)
        new_level = (profile.total_points // 100) + 1
        if new_level > profile.current_level:
            profile.current_level = new_level
        
        # Award achievement: First Exercise
        if service.should_award_achievement(
            profile, "first_exercise_submitted", current_user.id
        ):
            ach = Achievement.query.filter_by(code="first_exercise_submitted").first()
            if ach and not UserAchievement.query.filter_by(
                profile_id=profile.id, achievement_id=ach.id
            ).first():
                user_ach = UserAchievement(
                    profile_id=profile.id,
                    achievement_id=ach.id
                )
                db.session.add(user_ach)
                profile.total_points += ach.points_reward
        
        # Award achievement: Perfect Score (100% on module)
        if enrollment.passed and not enrollment.certificate:
            ach = Achievement.query.filter_by(code="module_completed").first()
            if ach and not UserAchievement.query.filter_by(
                profile_id=profile.id, achievement_id=ach.id
            ).first():
                user_ach = UserAchievement(
                    profile_id=profile.id,
                    achievement_id=ach.id
                )
                db.session.add(user_ach)
                profile.total_points += ach.points_reward
        
        db.session.commit()
    
    # Record analytics event
    track_event(
        feature="e_learning",
        action="submit_exercise",
        label=exercise.code,
        numeric_value=result.get("points_earned", 0),
        extra={"is_correct": result["is_correct"], "module_id": module_id},
    )

    return jsonify({
        "success": True,
        "is_correct": result["is_correct"],
        "points_earned": result["points_earned"],
        "feedback": result["feedback"],
        "result": result.get("result"),
        "error": result.get("error"),
    })


@bp.route("/api/execute-query", methods=["POST"])
@login_required
def api_execute_query():
    """Execute SQL query for practice (read-only or DML based on module type)."""
    data = request.json or {}
    module_id = data.get("module_id")
    query = data.get("query")
    
    if not all([module_id, query]):
        return jsonify({"error": "Missing module_id or query"}), 400
    
    module = ELearningModule.query.get_or_404(module_id)
    
    try:
        result = service.execute_query(
            module=module,
            user_id=current_user.id,
            query=query
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/reset-database/<int:module_id>", methods=["POST"])
@login_required
def api_reset_database(module_id):
    """Reset sample database to initial state."""
    module = ELearningModule.query.get_or_404(module_id)
    
    result = service.reset_sample_database(
        module=module,
        user_id=current_user.id
    )
    
    return jsonify({
        "success": True,
        "message": tr("database_reset"),
        "result": result
    })


@bp.route("/api/check-progress/<int:module_id>", methods=["GET"])
@login_required
def api_check_progress(module_id):
    """Get user's progress stats for a module."""
    module = ELearningModule.query.get_or_404(module_id)
    enrollment = UserELearningEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first_or_404()
    
    progress = service.calculate_progress(enrollment)
    
    return jsonify({
        "progress_percentage": progress["percentage"],
        "overall_score": enrollment.overall_score,
        "passed": enrollment.passed,
        "status": enrollment.status,
        "lessons_completed": progress["lessons_completed"],
        "total_lessons": module.total_lessons,
        "exercises_completed": progress["exercises_completed"],
        "total_exercises": module.total_exercises,
    })


@bp.route("/api/get-schema/<int:module_id>", methods=["GET"])
@login_required
def api_get_schema(module_id):
    """Get database schema for visualization."""
    module = ELearningModule.query.get_or_404(module_id)
    
    schema = service.get_database_schema(
        module=module,
        user_id=current_user.id
    )
    
    return jsonify(schema)


@bp.route("/api/complete-module/<int:module_id>", methods=["POST"])
@login_required
def api_complete_module(module_id):
    """Mark module as completed and generate certificate if passed."""
    module = ELearningModule.query.get_or_404(module_id)
    enrollment = UserELearningEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first_or_404()
    
    # Check if passed
    if not enrollment.passed:
        return jsonify({
            "error": tr("module_not_passed"),
            "progress": enrollment.progress_percentage,
            "pass_threshold": module.pass_threshold
        }), 400
    
    # Mark as completed
    enrollment.status = "completed"
    enrollment.completed_at = datetime.utcnow()
    db.session.commit()
    
    # Generate certificate
    cert = service.generate_certificate(
        enrollment=enrollment,
        module=module,
        user_id=current_user.id
    )
    
    # Award achievement: Module Completed
    profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        profile.modules_completed += 1
        ach = Achievement.query.filter_by(code="module_completed").first()
        if ach:
            profile.total_points += ach.points_reward
        db.session.commit()
    
    return jsonify({
        "success": True,
        "certificate_id": cert.id,
        "certificate_number": cert.certificate_number,
        "verification_code": cert.verification_code,
        "message": tr("module_completed_certificate_issued"),
    })


@bp.route("/api/leaderboard", methods=["GET"])
def api_leaderboard():
    """Get leaderboard data."""
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    # Get top users
    top_users = db.session.query(
        UserELearningProfile
    ).order_by(
        UserELearningProfile.total_points.desc()
    ).limit(limit).offset(offset).all()
    
    leaderboard = []
    for idx, profile in enumerate(top_users, start=1):
        leaderboard.append({
            "rank": idx,
            "user_id": profile.user_id,
            "username": profile.user.username if profile.user else "Unknown",
            "points": profile.total_points,
            "level": profile.current_level,
            "streak": profile.current_streak,
        })
    
    return jsonify(leaderboard)


@bp.route("/api/user-achievements", methods=["GET"])
@login_required
def api_user_achievements():
    """Get user's achievements."""
    profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
    
    if not profile:
        return jsonify({"achievements": []})
    
    achievements = db.session.query(UserAchievement, Achievement).join(
        Achievement
    ).filter(
        UserAchievement.profile_id == profile.id
    ).all()
    
    result = []
    for user_ach, ach in achievements:
        result.append({
            "id": ach.id,
            "code": ach.code,
            "name": ach.name_i18n,
            "description": ach.description_i18n,
            "icon_url": ach.icon_url,
            "rarity": ach.rarity,
            "points_reward": ach.points_reward,
            "earned_at": user_ach.earned_at.isoformat(),
        })
    
    return jsonify({"achievements": result})


@bp.route("/api/progress-report", methods=["GET"])
@login_required
def api_progress_report():
    """Get comprehensive progress report."""
    profile = UserELearningProfile.query.filter_by(user_id=current_user.id).first()
    
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    
    # Get all enrollments
    enrollments = UserELearningEnrollment.query.filter_by(user_id=current_user.id).all()
    
    # Get all submissions
    submissions = db.session.query(UserELearningSubmission).filter(
        UserELearningSubmission.user_id == current_user.id
    ).all()
    
    # Get certificates
    certificates = ELearningCertificate.query.filter_by(user_id=current_user.id).all()
    
    # Calculate stats
    total_exercises = len(submissions)
    correct_exercises = len([s for s in submissions if s.is_correct])
    accuracy = (correct_exercises / total_exercises * 100) if total_exercises > 0 else 0
    
    total_modules = len(enrollments)
    completed_modules = len([e for e in enrollments if e.status == "completed"])
    
    return jsonify({
        "profile": {
            "total_points": profile.total_points,
            "current_level": profile.current_level,
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "modules_completed": profile.modules_completed,
            "exercises_completed": profile.exercises_completed,
        },
        "stats": {
            "total_modules": total_modules,
            "completed_modules": completed_modules,
            "completion_rate": (completed_modules / total_modules * 100) if total_modules > 0 else 0,
            "total_exercises": total_exercises,
            "correct_exercises": correct_exercises,
            "accuracy": accuracy,
            "total_certificates": len(certificates),
        },
        "enrollments": [
            {
                "module_id": e.module_id,
                "module_name": e.module.title_i18n,
                "status": e.status,
                "progress": e.progress_percentage,
                "score": e.overall_score,
                "enrolled_at": e.enrolled_at.isoformat(),
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            }
            for e in enrollments
        ],
    })


@bp.route("/api/exercises-summary", methods=["GET"])
@login_required
def api_exercises_summary():
    """Get summary of all exercises with results."""
    submissions = db.session.query(
        UserELearningSubmission
    ).filter(
        UserELearningSubmission.user_id == current_user.id
    ).order_by(UserELearningSubmission.submitted_at.desc()).all()
    
    result = []
    seen_exercises = set()
    
    for submission in submissions:
        exercise_id = submission.exercise_id
        if exercise_id in seen_exercises:
            continue
        
        seen_exercises.add(exercise_id)
        exercise = ELearningExercise.query.get(exercise_id)
        lesson = exercise.lesson if exercise else None
        module = lesson.module if lesson else None
        
        # Get best attempt
        best_submission = db.session.query(UserELearningSubmission).filter(
            UserELearningSubmission.exercise_id == exercise_id,
            UserELearningSubmission.user_id == current_user.id
        ).order_by(UserELearningSubmission.points_earned.desc()).first()
        
        result.append({
            "exercise_id": exercise_id,
            "exercise_name": exercise.title_i18n if exercise else "Unknown",
            "module_name": module.title_i18n if module else "Unknown",
            "attempts": db.session.query(UserELearningSubmission).filter(
                UserELearningSubmission.exercise_id == exercise_id,
                UserELearningSubmission.user_id == current_user.id
            ).count(),
            "best_score": best_submission.points_earned if best_submission else 0,
            "correct": best_submission.is_correct if best_submission else False,
            "last_attempt": submission.submitted_at.isoformat(),
        })
    
    return jsonify({"exercises": result})


@bp.route("/api/certificates-list", methods=["GET"])
@login_required
def api_certificates_list():
    """Get list of all user certificates."""
    certificates = ELearningCertificate.query.filter_by(user_id=current_user.id).order_by(
        ELearningCertificate.issued_at.desc()
    ).all()
    
    result = []
    for cert in certificates:
        result.append({
            "id": cert.id,
            "certificate_number": cert.certificate_number,
            "module_name": cert.module.title_i18n if cert.module else "Unknown",
            "subject_name": cert.module.subject.name_i18n if cert.module else "Unknown",
            "final_score": cert.final_score,
            "issued_at": cert.issued_at.isoformat(),
            "verification_code": cert.verification_code,
            "is_public": cert.is_public,
            "viewed_count": cert.viewed_count,
        })
    
    return jsonify({"certificates": result})


@bp.route("/download/certificate/<int:cert_id>/pdf", methods=["GET"])
@login_required
def download_certificate_pdf(cert_id):
    """Download individual certificate as PDF."""
    cert = ELearningCertificate.query.filter_by(
        id=cert_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Certificate content
    from reportlab.lib.colors import HexColor
    title_style = styles['Heading1']
    title_style.alignment = 1  # Center
    
    story.append(Spacer(1, 1 * inch))
    story.append(Paragraph(tr("Certificate of Completion"), title_style))
    story.append(Spacer(1, 0.5 * inch))
    
    story.append(Paragraph(f"<b>{tr('This certifies that')}</b>", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"<b>{current_user.username}</b>", title_style))
    story.append(Spacer(1, 0.3 * inch))
    
    cert_text = f"{tr('has successfully completed')} <b>{cert.module.title_i18n.get('en', cert.module.code)}</b>"
    story.append(Paragraph(cert_text, styles['Normal']))
    
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph(f"<b>{tr('Final Score')}: {cert.final_score}%</b>", styles['Normal']))
    
    story.append(Spacer(1, 1 * inch))
    story.append(Paragraph(f"{tr('Certificate Number')}: {cert.certificate_number}", styles['Normal']))
    story.append(Paragraph(f"{tr('Issued On')}: {cert.issued_at.strftime('%d/%m/%Y')}", styles['Normal']))
    story.append(Paragraph(f"{tr('Verification Code')}: {cert.verification_code}", styles['Normal']))
    
    doc.build(story)
    pdf_buffer.seek(0)
    
    track_event(
        feature="e_learning",
        action="download_certificate_pdf",
        label=cert.certificate_number,
        extra={"cert_id": cert_id},
    )

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"certificate_{cert.certificate_number}.pdf"
    )


@bp.route("/download/all-certificates/zip", methods=["GET"])
@login_required
def download_all_certificates_zip():
    """Download all certificates as ZIP file."""
    certificates = ELearningCertificate.query.filter_by(user_id=current_user.id).all()
    
    if not certificates:
        return jsonify({"error": "No certificates found"}), 404
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for cert in certificates:
            # Create PDF for each certificate
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            story.append(Spacer(1, 1 * inch))
            story.append(Paragraph(tr("Certificate of Completion"), styles['Heading1']))
            story.append(Spacer(1, 0.5 * inch))
            story.append(Paragraph(f"<b>{tr('This certifies that')}</b>", styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph(f"<b>{current_user.username}</b>", styles['Heading1']))
            story.append(Spacer(1, 0.3 * inch))
            
            story.append(Paragraph(
                f"{tr('has successfully completed')} <b>{cert.module.title_i18n.get('en', cert.module.code)}</b>",
                styles['Normal']
            ))
            story.append(Spacer(1, 0.5 * inch))
            story.append(Paragraph(f"<b>{tr('Final Score')}: {cert.final_score}%</b>", styles['Normal']))
            
            doc.build(story)
            pdf_buffer.seek(0)
            
            # Add to ZIP
            zf.writestr(f"certificate_{cert.certificate_number}.pdf", pdf_buffer.getvalue())
    
    zip_buffer.seek(0)
    
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"certificates_{current_user.id}.zip"
    )


@bp.route("/download/progress-report/csv", methods=["GET"])
@login_required
def download_progress_report_csv():
    """Download progress report as CSV."""
    enrollments = UserELearningEnrollment.query.filter_by(user_id=current_user.id).all()
    
    # Create CSV in memory
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=[
        'Module', 'Subject', 'Status', 'Progress (%)', 'Score (%)', 
        'Enrolled Date', 'Completed Date'
    ])
    
    writer.writeheader()
    for enrollment in enrollments:
        writer.writerow({
            'Module': enrollment.module.title_i18n.get('en', enrollment.module.code),
            'Subject': enrollment.module.subject.name_i18n.get('en', enrollment.module.subject.code),
            'Status': enrollment.status,
            'Progress (%)': enrollment.progress_percentage,
            'Score (%)': enrollment.overall_score,
            'Enrolled Date': enrollment.enrolled_at.strftime('%d/%m/%Y'),
            'Completed Date': enrollment.completed_at.strftime('%d/%m/%Y') if enrollment.completed_at else 'N/A',
        })
    
    # Convert to bytes
    csv_bytes = io.BytesIO(csv_buffer.getvalue().encode())
    
    return send_file(
        csv_bytes,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"progress_report_{current_user.id}.csv"
    )
