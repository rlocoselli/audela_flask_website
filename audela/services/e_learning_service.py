"""
E-Learning Service - Core business logic for multi-subject learning platform

Handles:
- SQL sandbox execution (SQL subject)
- Exercise evaluation
- Progress tracking
- Certificate generation
- Gamification (achievements, points, streaks, levels)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import string
import tempfile
import time
from datetime import datetime, timedelta, date
from pathlib import Path
from random import choices
from typing import Any, Optional

from sqlalchemy import func, text

from ..extensions import db
from ..models.e_learning import (
    ELearningModule,
    ELearningExercise,
    UserELearningEnrollment,
    UserELearningSubmission,
    ELearningCertificate,
    ELearningSampleDatabase,
    UserELearningProfile,
)
from ..i18n import DEFAULT_LANG, SUPPORTED_LANGS, tr

logger = logging.getLogger(__name__)


class ELearningSandboxError(Exception):
    """Raised when SQL execution or validation fails."""
    pass


class ELearningService:
    """Service for e-learning platform operations."""
    
    def __init__(self):
        self.sandbox_dir = Path(tempfile.gettempdir()) / "audela_e_learning"
        self.sandbox_dir.mkdir(exist_ok=True)
    
    # ===== SQL SANDBOX OPERATIONS =====
    
    def get_or_create_sample_database(self, user_id: int, module_id: int) -> ELearningSampleDatabase:
        """Get or create a sample database for user + module (SQL subject)."""
        sample_db = ELearningSampleDatabase.query.filter_by(
            user_id=user_id,
            module_id=module_id
        ).first()
        
        if not sample_db:
            module = ELearningModule.query.get(module_id)
            if not module or module.subject.code != "sql":
                raise ELearningSandboxError("Module is not a SQL module")
            
            db_file_path = self._create_sandbox_database(module, user_id)
            
            sample_db = ELearningSampleDatabase(
                module_id=module_id,
                user_id=user_id,
                db_file_path=db_file_path,
                is_initialized=True,
                last_reset_at=datetime.utcnow()
            )
            db.session.add(sample_db)
            db.session.commit()
        
        return sample_db
    
    def _create_sandbox_database(self, module: ELearningModule, user_id: int) -> str:
        """Create SQLite database with module's sample schema and data."""
        db_filename = f"e_learning_{module.id}_{user_id}_{int(time.time())}.db"
        db_file_path = str(self.sandbox_dir / db_filename)
        
        try:
            conn = sqlite3.connect(db_file_path)
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            
            # Create schema
            if module.sample_database_schema:
                cursor.executescript(module.sample_database_schema)
            
            # Insert sample data
            if module.sample_data_sql:
                cursor.executescript(module.sample_data_sql)
            
            conn.commit()
            conn.close()
            
            logger.info(f"Created sandbox database: {db_file_path}")
            return db_file_path
        
        except Exception as e:
            logger.error(f"Error creating sandbox database: {e}", exc_info=True)
            raise ELearningSandboxError(f"Failed to create sample database: {e}")
    
    def execute_query(
        self,
        module: ELearningModule,
        user_id: int,
        query: str,
        timeout: int = 30
    ) -> dict[str, Any]:
        """Execute a SQL query in the user's sandbox."""
        sample_db = self.get_or_create_sample_database(user_id, module.id)
        
        if not os.path.exists(sample_db.db_file_path):
            raise ELearningSandboxError("Sample database not found")
        
        start_time = time.time()
        
        try:
            conn = sqlite3.connect(sample_db.db_file_path, timeout=timeout)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            
            query = query.strip()
            if not query:
                raise ELearningSandboxError("Query cannot be empty")
            
            cursor.execute(query)
            rows = cursor.fetchall() if cursor.description else []
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            affected_rows = 0

            if cursor.description:
                result_data = [dict(row) for row in rows]
            else:
                conn.commit()
                result_data = []
                affected_rows = max(cursor.rowcount, 0)
            execution_time_ms = (time.time() - start_time) * 1000
            
            conn.close()
            
            return {
                "success": True,
                "result_data": result_data,
                "columns": columns,
                "row_count": len(result_data) if columns else affected_rows,
                "affected_rows": affected_rows,
                "execution_time_ms": execution_time_ms
            }
        
        except sqlite3.Error as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "error": f"SQL Error: {e}",
                "execution_time_ms": execution_time_ms
            }
        except Exception as e:
            logger.error(f"Error executing query: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def reset_sample_database(self, module: ELearningModule, user_id: int) -> dict:
        """Reset sample database to initial state."""
        sample_db = ELearningSampleDatabase.query.filter_by(
            user_id=user_id,
            module_id=module.id
        ).first()
        
        if sample_db and os.path.exists(sample_db.db_file_path):
            try:
                os.remove(sample_db.db_file_path)
            except Exception as e:
                logger.warning(f"Could not delete old database: {e}")
            
            db.session.delete(sample_db)
            db.session.commit()
        
        # Create new database
        sample_db = self.get_or_create_sample_database(user_id, module.id)
        
        return {"success": True, "message": "Database reset"}
    
    # ===== EXERCISE EVALUATION =====
    
    def execute_and_evaluate_exercise(
        self,
        exercise: ELearningExercise,
        module: ELearningModule,
        user_id: int,
        submitted_sql: str,
        enrollment: UserELearningEnrollment
    ) -> dict[str, Any]:
        """Execute user's submission and evaluate correctness."""
        
        # Get attempt number
        attempt_count = UserELearningSubmission.query.filter_by(
            user_id=user_id,
            exercise_id=exercise.id
        ).count()
        attempt_number = attempt_count + 1
        
        is_correct = False
        points_earned = 0
        feedback = {}
        result = None
        error_message = None
        
        try:
            # Execute query
            exec_result = self.execute_query(module, user_id, submitted_sql)
            
            if not exec_result["success"]:
                error_message = exec_result.get("error", "Unknown error")
                feedback = self._generate_feedback(False, error_message, DEFAULT_LANG)
            else:
                result = exec_result
                
                # Evaluate correctness
                if exercise.type == "sql_query":
                    is_correct = self._evaluate_query_result(exec_result["result_data"], exercise)
                
                elif exercise.type == "sql_dml":
                    if not exercise.validation_query:
                        error_message = "Exercise validation is not configured for this SQL change task."
                        feedback = self._generate_feedback(False, error_message, DEFAULT_LANG)
                    else:
                        validation_result = self.execute_query(module, user_id, exercise.validation_query)
                        if validation_result["success"]:
                            is_correct = self._evaluate_dml_result(validation_result["result_data"], exercise)
                        else:
                            error_message = validation_result.get("error", "Validation query failed")
                            feedback = self._generate_feedback(False, error_message, DEFAULT_LANG)
                
                if not feedback:
                    feedback = self._generate_feedback(is_correct, None, DEFAULT_LANG)
        
        except Exception as e:
            logger.error(f"Error evaluating exercise: {e}", exc_info=True)
            error_message = str(e)
            feedback = self._generate_feedback(False, str(e), DEFAULT_LANG)
        
        # Award points if correct
        if is_correct:
            points_earned = exercise.points
        
        # Update progress and recalculate score percentage
        enrollment.progress_percentage = self._calculate_progress_percentage(enrollment, module)
        enrollment.overall_score = self._calculate_overall_score(enrollment, module)
        enrollment.passed = enrollment.overall_score >= module.pass_threshold
        
        # Record submission
        submission = UserELearningSubmission(
            enrollment_id=enrollment.id,
            exercise_id=exercise.id,
            user_id=user_id,
            submitted_sql=submitted_sql,
            is_correct=is_correct,
            points_earned=points_earned,
            feedback_i18n=feedback,
            result_json=result,
            error_message=error_message,
            attempt_number=attempt_number
        )
        db.session.add(submission)
        db.session.commit()
        
        return {
            "is_correct": is_correct,
            "points_earned": points_earned,
            "feedback": feedback.get(DEFAULT_LANG, ""),
            "result": result,
            "error": error_message,
            "attempt_number": attempt_number
        }
    
    def _evaluate_query_result(self, result_data: list, exercise: ELearningExercise) -> bool:
        """Check if query result matches expected result."""
        if exercise.expected_result_json is None:
            return len(result_data) > 0  # At least return something
        
        expected = exercise.expected_result_json
        return result_data == expected
    
    def _evaluate_dml_result(self, validation_result: list, exercise: ELearningExercise) -> bool:
        """Check if DML validation query passes."""
        if exercise.expected_result_json is None:
            return len(validation_result) > 0
        
        expected = exercise.expected_result_json
        return validation_result == expected
    
    def _generate_feedback(self, is_correct: bool, error: Optional[str], language: str) -> dict:
        """Generate multi-language feedback."""
        if is_correct:
            feedback_text = tr("exercise_correct")
        elif error:
            feedback_text =f"Error: {error}"
        else:
            feedback_text = tr("exercise_incorrect")
        
        return {
            language: feedback_text,
            "en": feedback_text  # Fallback
        }
    
    def _calculate_progress_percentage(self, enrollment: UserELearningEnrollment, module: ELearningModule) -> int:
        """Calculate module progress percentage."""
        if module.total_exercises == 0:
            return 0
        
        submissions = UserELearningSubmission.query.filter_by(
            enrollment_id=enrollment.id
        ).filter(
            UserELearningSubmission.is_correct == True
        ).count()
        
        percentage = int((submissions / module.total_exercises) * 100)
        return min(100, percentage)
    
    def _calculate_overall_score(self, enrollment: UserELearningEnrollment, module: ELearningModule) -> int:
        """Calculate overall score as a percentage based on points earned."""
        # Get total points from correct submissions
        correct_submissions = UserELearningSubmission.query.filter_by(
            enrollment_id=enrollment.id,
            is_correct=True
        ).all()
        
        total_points_earned = sum(sub.points_earned for sub in correct_submissions)
        
        # Get total possible points
        total_possible_points = sum(e.points for lesson in module.lessons for e in lesson.exercises)
        
        if total_possible_points == 0:
            return 0
        
        percentage = int((total_points_earned / total_possible_points) * 100)
        return min(100, percentage)
    
    # ===== PROGRESS TRACKING =====
    
    def calculate_progress(self, enrollment: UserELearningEnrollment) -> dict[str, Any]:
        """Calculate detailed progress for enrollment."""
        module = enrollment.module
        
        correct_submissions = UserELearningSubmission.query.filter_by(
            enrollment_id=enrollment.id,
            is_correct=True
        ).count()
        
        total_submissions = UserELearningSubmission.query.filter_by(
            enrollment_id=enrollment.id
        ).count()
        
        return {
            "percentage": enrollment.progress_percentage,
            "exercises_completed": correct_submissions,
            "total_exercises": module.total_exercises,
            "lessons_completed": len([l for l in module.lessons if l.is_active]),
            "correct_submissions": correct_submissions,
            "total_submissions": total_submissions,
        }
    
    def get_database_schema(self, module: ELearningModule, user_id: int) -> dict[str, Any]:
        """Get database schema for visualization and guided exploration."""
        sample_db = self.get_or_create_sample_database(user_id, module.id)
        
        try:
            conn = sqlite3.connect(sample_db.db_file_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            tables = cursor.fetchall()
            
            schema = []
            relationships: list[dict[str, Any]] = []
            for (table_name,) in tables:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                foreign_keys = cursor.fetchall()
                cursor.execute(f'SELECT COUNT(*) AS row_count FROM "{table_name}"')
                row_count = int(cursor.fetchone()[0] or 0)
                cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 5')
                sample_rows = [dict(row) for row in cursor.fetchall()]
                primary_keys = [col[1] for col in columns if col[5]]
                
                table_info = {
                    "name": table_name,
                    "columns": [
                        {
                            "name": col[1],
                            "type": col[2],
                            "notnull": col[3],
                            "pk": col[5]
                        }
                        for col in columns
                    ],
                    "primary_keys": primary_keys,
                    "foreign_keys": [
                        {
                            "from_column": fk[3],
                            "to_table": fk[2],
                            "to_column": fk[4],
                        }
                        for fk in foreign_keys
                    ],
                    "row_count": row_count,
                    "sample_rows": sample_rows,
                }
                schema.append(table_info)

                for fk in foreign_keys:
                    relationships.append(
                        {
                            "from_table": table_name,
                            "from_column": fk[3],
                            "to_table": fk[2],
                            "to_column": fk[4],
                            "label": f"{table_name}.{fk[3]} -> {fk[2]}.{fk[4]}",
                        }
                    )
            
            conn.close()

            return {
                "schema": schema,
                "relationships": relationships,
                "table_count": len(schema),
                "relationship_count": len(relationships),
                "exploration_tips": [
                    tr("Start with the primary entities before joining related tables."),
                    tr("Use foreign-key arrows to understand how rows connect across the model."),
                    tr("Preview the sample rows before writing SQL so you can spot useful filters and aggregations."),
                ],
            }
        
        except Exception as e:
            logger.error(f"Error getting schema: {e}", exc_info=True)
            return {"error": str(e)}
    
    # ===== GAMIFICATION =====
    
    def should_award_achievement(
        self,
        profile: UserELearningProfile,
        achievement_code: str,
        user_id: int
    ) -> bool:
        """Check if user should be awarded an achievement."""
        from ..models.e_learning import Achievement, UserAchievement
        
        ach = Achievement.query.filter_by(code=achievement_code).first()
        if not ach:
            return False
        
        # Check if already has achievement
        already_has = UserAchievement.query.filter_by(
            profile_id=profile.id,
            achievement_id=ach.id
        ).first()
        
        return not already_has
    
    def update_streak(self, profile: UserELearningProfile) -> dict:
        """Update user's streak (consecutive days of activity)."""
        today = date.today()
        
        if profile.last_streak_date is None:
            # First activity
            profile.current_streak = 1
            profile.last_streak_date = today
        elif profile.last_streak_date == today:
            # Already updated today
            pass
        elif (today - profile.last_streak_date).days == 1:
            # Consecutive day
            profile.current_streak += 1
            profile.longest_streak = max(profile.longest_streak, profile.current_streak)
            profile.last_streak_date = today
        else:
            # Streak broken
            profile.current_streak = 1
            profile.last_streak_date = today
        
        db.session.commit()
        return {"current_streak": profile.current_streak, "longest_streak": profile.longest_streak}
    
    # ===== CERTIFICATE GENERATION =====
    
    def generate_certificate(
        self,
        enrollment: UserELearningEnrollment,
        module: ELearningModule,
        user_id: int
    ) -> ELearningCertificate:
        """Generate certificate upon module completion."""
        cert_num = self._generate_certificate_number(module, user_id)
        verification_code = self._generate_verification_code()
        
        cert = ELearningCertificate(
            enrollment_id=enrollment.id,
            user_id=user_id,
            module_id=module.id,
            certificate_number=cert_num,
            final_score=enrollment.overall_score,
            verification_code=verification_code,
            is_public=True
        )
        db.session.add(cert)
        db.session.commit()
        
        logger.info(f"Generated certificate {cert_num} for user {user_id} on module {module.id}")
        return cert
    
    def _generate_certificate_number(self, module: ELearningModule, user_id: int) -> str:
        """Generate unique certificate number."""
        timestamp = int(time.time() * 1000)  # milliseconds
        cert_num = f"{module.subject.code.upper()}-{user_id}-{timestamp}"
        return cert_num
    
    def _generate_verification_code(self, length: int = 12) -> str:
        """Generate random verification code."""
        chars = string.ascii_letters + string.digits
        return "".join(choices(chars, k=length))
    
    def get_certificate_html(
        self,
        certificate: ELearningCertificate,
        language: str = DEFAULT_LANG
    ) -> str:
        """Render beautiful certificate HTML for display/PDF."""
        module = certificate.module
        subject = module.subject
        user = certificate.user
        
        issue_date = certificate.issued_at.strftime("%d/%m/%Y")
        
        html = f"""
        <div class="certificate-container">
            <div class="certificate">
                <div class="certificate-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                    <h1>{tr('certificate_of_completion')}</h1>
                </div>
                
                <div class="certificate-body">
                    <p class="certificate-recipient">
                        {tr('this_certifies_that')}
                        <strong>{user.username if user else 'User'}</strong>
                    </p>
                    
                    <p class="certificate-text">
                        {tr('has_successfully_completed')} <strong>{module.title_i18n.get(language, module.title_i18n.get('en', module.code))}</strong>
                        {tr('in')} <strong>{subject.name_i18n.get(language, subject.name_i18n.get('en', subject.code))}</strong>
                    </p>
                    
                    <p class="certificate-score">
                        {tr('final_score')}: <strong>{certificate.final_score}%</strong>
                    </p>
                    
                    <div class="certificate-footer">
                        <div class="cert-number">
                            {tr('certificate_number')}: {certificate.certificate_number}
                        </div>
                        <div class="cert-date">
                            {tr('issued_on')}: {issue_date}
                        </div>
                        <div class="cert-code">
                            {tr('verification_code')}: {certificate.verification_code}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """
        
        return html
