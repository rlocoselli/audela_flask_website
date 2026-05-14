"""
SQL Training API Routes - Backend for exercise submissions and SQL execution
"""

from __future__ import annotations

import logging
import json
from datetime import datetime

from flask import abort, jsonify, request
from flask_login import current_user, login_required

from ...extensions import db
from ...models.sql_training import (
    SQLTrainingExercise,
    SQLTrainingLesson,
    UserSQLTrainingEnrollment,
    UserSQLTrainingSubmission,
    SQLTrainingCertificate,
)
from ...services.sql_training_service import SQLTrainingService
from ...i18n import SUPPORTED_LANGS, DEFAULT_LANG

from . import bp

logger = logging.getLogger(__name__)


@bp.route("/api/submit-exercise", methods=["POST"])
@login_required
def api_submit_exercise():
    """
    Submit SQL code for an exercise.
    
    Expected JSON:
    {
        "exercise_id": int,
        "enrollment_id": int,
        "sql_code": str,
        "lang": str (optional)
    }
    """
    data = request.get_json() or {}
    
    exercise_id = data.get("exercise_id")
    enrollment_id = data.get("enrollment_id")
    sql_code = data.get("sql_code", "")
    lang = data.get("lang", DEFAULT_LANG)
    
    if not exercise_id or not enrollment_id or not sql_code:
        return jsonify({"error": "Missing required fields"}), 400
    
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    
    # Verify enrollment belongs to current user
    enrollment = UserSQLTrainingEnrollment.query.get(enrollment_id)
    if not enrollment or enrollment.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get exercise
    exercise = SQLTrainingExercise.query.get_or_404(exercise_id)
    if exercise.lesson.module_id != enrollment.module_id:
        return jsonify({"error": "Exercise not in this module"}), 400
    
    # Execute SQL and evaluate
    service = SQLTrainingService()
    
    try:
        result = service.execute_and_evaluate_exercise(
            exercise=exercise,
            enrollment=enrollment,
            sql_code=sql_code,
            user_language=lang
        )
        
        # Create submission record
        submission = UserSQLTrainingSubmission(
            enrollment_id=enrollment_id,
            exercise_id=exercise_id,
            user_id=current_user.id,
            submitted_sql=sql_code,
            is_correct=result["is_correct"],
            points_earned=result["points_earned"],
            feedback_i18n=result.get("feedback_i18n", {}),
            result_json=result.get("result_data", {}),
            execution_time_ms=result.get("execution_time_ms"),
            error_message=result.get("error_message"),
            attempt_number=result.get("attempt_number", 1)
        )
        db.session.add(submission)
        
        # Update enrollment scores if this is the best attempt so far
        best_score = db.session.query(db.func.max(UserSQLTrainingSubmission.points_earned)).filter_by(
            enrollment_id=enrollment_id,
            exercise_id=exercise_id
        ).scalar() or 0
        
        if result["points_earned"] > best_score:
            # Update progress JSON in enrollment
            if not enrollment.lessons_progress_json:
                enrollment.lessons_progress_json = {}
            
            lesson_id = exercise.lesson_id
            if lesson_id not in enrollment.lessons_progress_json:
                enrollment.lessons_progress_json[lesson_id] = {}
            
            enrollment.lessons_progress_json[lesson_id][exercise_id] = {
                "completed": result["is_correct"],
                "score": result["points_earned"],
                "max_score": exercise.points
            }
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "is_correct": result["is_correct"],
            "points_earned": result["points_earned"],
            "feedback": result.get("feedback_i18n", {}),
            "result": result.get("result_data"),
            "execution_time_ms": result.get("execution_time_ms"),
            "error_message": result.get("error_message"),
        })
    
    except Exception as e:
        logger.error(f"Error executing exercise: {e}", exc_info=True)
        return jsonify({
            "error": "Error executing SQL",
            "message": str(e)
        }), 500


@bp.route("/api/execute-query", methods=["POST"])
@login_required
def api_execute_query():
    """
    Execute arbitrary SQL query for practice (sandbox mode).
    
    Expected JSON:
    {
        "query": str,
        "module_id": int
    }
    """
    data = request.get_json() or {}
    
    query = data.get("query", "").strip()
    module_id = data.get("module_id")
    
    if not query or not module_id:
        return jsonify({"error": "Missing query or module_id"}), 400
    
    # Verify enrollment in module
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first()
    
    if not enrollment:
        return jsonify({"error": "Not enrolled in this module"}), 403
    
    service = SQLTrainingService()
    
    try:
        result = service.execute_query(
            module_id=module_id,
            user_id=current_user.id,
            query=query
        )
        
        return jsonify({
            "success": True,
            "result": result.get("result_data", []),
            "columns": result.get("columns", []),
            "row_count": result.get("row_count", 0),
            "execution_time_ms": result.get("execution_time_ms"),
        })
    
    except Exception as e:
        logger.error(f"Error executing query: {e}", exc_info=True)
        return jsonify({
            "error": "Error executing query",
            "message": str(e)
        }), 500


@bp.route("/api/reset-database/<int:module_id>", methods=["POST"])
@login_required
def api_reset_database(module_id: int):
    """Reset user's sample database to initial state."""
    # Verify enrollment
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first_or_404()
    
    service = SQLTrainingService()
    
    try:
        service.reset_sample_database(current_user.id, module_id)
        return jsonify({"success": True, "message": "Database reset successfully"})
    except Exception as e:
        logger.error(f"Error resetting database: {e}", exc_info=True)
        return jsonify({"error": "Error resetting database"}), 500


@bp.route("/api/check-progress/<int:module_id>", methods=["GET"])
@login_required
def api_check_progress(module_id: int):
    """Get user's progress in a module."""
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first_or_404()
    
    # Calculate progress
    service = SQLTrainingService()
    progress_data = service.calculate_progress(enrollment)
    
    return jsonify(progress_data)


@bp.route("/api/get-schema/<int:module_id>", methods=["GET"])
@login_required
def api_get_schema(module_id: int):
    """Get database schema information for the module."""
    # Verify enrollment
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first_or_404()
    
    service = SQLTrainingService()
    
    try:
        schema = service.get_database_schema(module_id, current_user.id)
        return jsonify({"success": True, "schema": schema})
    except Exception as e:
        logger.error(f"Error getting schema: {e}", exc_info=True)
        return jsonify({"error": "Error getting schema"}), 500


@bp.route("/api/autocomplete-sql", methods=["POST"])
@login_required
def api_autocomplete_sql():
    """
    Get SQL autocomplete suggestions based on schema.
    
    Expected JSON:
    {
        "query_prefix": str,
        "module_id": int,
        "context": str (optional)
    }
    """
    data = request.get_json() or {}
    
    query_prefix = data.get("query_prefix", "")
    module_id = data.get("module_id")
    
    if not query_prefix or not module_id:
        return jsonify({"suggestions": []})
    
    # Verify enrollment
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first_or_404()
    
    service = SQLTrainingService()
    suggestions = service.get_sql_suggestions(module_id, query_prefix)
    
    return jsonify({"suggestions": suggestions})


@bp.route("/api/complete-module/<int:module_id>", methods=["POST"])
@login_required
def api_complete_module(module_id: int):
    """Complete a module and generate certificate if passing."""
    enrollment = UserSQLTrainingEnrollment.query.filter_by(
        user_id=current_user.id,
        module_id=module_id
    ).first_or_404()
    
    service = SQLTrainingService()
    
    try:
        # Evaluate completion
        is_passed, final_score = service.evaluate_module_completion(enrollment)
        
        if is_passed:
            # Generate certificate
            certificate = service.generate_certificate(enrollment)
            
            enrollment.status = "completed"
            enrollment.completed_at = datetime.utcnow()
            enrollment.passed = True
            enrollment.overall_score = final_score
            db.session.commit()
            
            return jsonify({
                "success": True,
                "passed": True,
                "score": final_score,
                "certificate_id": certificate.id,
                "certificate_number": certificate.certificate_number,
                "verification_code": certificate.verification_code
            })
        else:
            return jsonify({
                "success": True,
                "passed": False,
                "score": final_score,
                "message": f"Need {enrollment.module.pass_threshold}% to pass"
            })
    
    except Exception as e:
        logger.error(f"Error completing module: {e}", exc_info=True)
        return jsonify({"error": "Error completing module"}), 500
