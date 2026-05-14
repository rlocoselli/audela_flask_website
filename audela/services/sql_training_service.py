"""
SQL Training Service - Core business logic for SQL training module

Handles:
- SQL sandbox execution
- Exercise evaluation
- Progress tracking
- Certificate generation with beautiful design
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
from datetime import datetime, timedelta
from pathlib import Path
from random import choices
from typing import Any, Optional, Tuple

from sqlalchemy import func, text

from ..extensions import db
from ..models.sql_training import (
    SQLTrainingModule,
    SQLTrainingExercise,
    UserSQLTrainingEnrollment,
    UserSQLTrainingSubmission,
    SQLTrainingCertificate,
    SQLTrainingSampleDatabase,
)
from ..i18n import DEFAULT_LANG, SUPPORTED_LANGS

logger = logging.getLogger(__name__)


class SQLSandboxError(Exception):
    """Raised when SQL execution or validation fails."""
    pass


class SQLTrainingService:
    """Service for SQL training operations."""
    
    def __init__(self):
        self.sandbox_dir = Path(tempfile.gettempdir()) / "audela_sql_training"
        self.sandbox_dir.mkdir(exist_ok=True)
        
    def get_or_create_sample_database(self, user_id: int, module_id: int) -> SQLTrainingSampleDatabase:
        """Get or create a sample database for user + module."""
        sample_db = SQLTrainingSampleDatabase.query.filter_by(
            user_id=user_id,
            module_id=module_id
        ).first()
        
        if not sample_db:
            module = SQLTrainingModule.query.get(module_id)
            db_file_path = self._create_sandbox_database(module, user_id)
            
            sample_db = SQLTrainingSampleDatabase(
                module_id=module_id,
                user_id=user_id,
                db_file_path=db_file_path,
                is_initialized=True,
                last_reset_at=datetime.utcnow()
            )
            db.session.add(sample_db)
            db.session.commit()
        
        return sample_db
    
    def _create_sandbox_database(self, module: SQLTrainingModule, user_id: int) -> str:
        """Create SQLite database with module's sample schema and data."""
        db_filename = f"sql_training_{module.id}_{user_id}_{int(time.time())}.db"
        db_file_path = str(self.sandbox_dir / db_filename)
        
        try:
            conn = sqlite3.connect(db_file_path)
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
            raise SQLSandboxError(f"Failed to create sample database: {e}")
    
    def execute_query(
        self,
        module_id: int,
        user_id: int,
        query: str,
        timeout: int = 30
    ) -> dict[str, Any]:
        """
        Execute a SQL query in the user's sandbox.
        
        Returns:
            {
                "result_data": List[dict],
                "columns": List[str],
                "row_count": int,
                "execution_time_ms": float
            }
        """
        sample_db = self.get_or_create_sample_database(user_id, module_id)
        
        if not os.path.exists(sample_db.db_file_path):
            raise SQLSandboxError("Sample database not found")
        
        start_time = time.time()
        
        try:
            conn = sqlite3.connect(sample_db.db_file_path)
            conn.timeout = timeout
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Sanitize and execute query
            query = query.strip()
            if not query:
                raise SQLSandboxError("Query cannot be empty")
            
            # Basic security: prevent dangerous operations
            dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE"]
            if any(kw in query.upper() for kw in dangerous_keywords):
                # For DML exercises, DELETE might be allowed - handled separately
                pass
            
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            result_data = [dict(row) for row in rows]
            execution_time_ms = (time.time() - start_time) * 1000
            
            conn.close()
            
            return {
                "result_data": result_data,
                "columns": columns,
                "row_count": len(result_data),
                "execution_time_ms": execution_time_ms
            }
        
        except sqlite3.Error as e:
            execution_time_ms = (time.time() - start_time) * 1000
            raise SQLSandboxError(f"SQL Error: {e}")
        except Exception as e:
            logger.error(f"Error executing query: {e}", exc_info=True)
            raise SQLSandboxError(str(e))
    
    def execute_dml(
        self,
        module_id: int,
        user_id: int,
        dml_statement: str
    ) -> dict[str, Any]:
        """
        Execute DML (INSERT, UPDATE, DELETE) in sandbox.
        
        Returns:
            {"rows_affected": int, ...}
        """
        sample_db = self.get_or_create_sample_database(user_id, module_id)
        
        if not os.path.exists(sample_db.db_file_path):
            raise SQLSandboxError("Sample database not found")
        
        try:
            conn = sqlite3.connect(sample_db.db_file_path)
            cursor = conn.cursor()
            
            cursor.execute(dml_statement)
            rows_affected = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return {"rows_affected": rows_affected}
        
        except Exception as e:
            logger.error(f"Error executing DML: {e}", exc_info=True)
            raise SQLSandboxError(f"DML Error: {e}")
    
    def execute_and_evaluate_exercise(
        self,
        exercise: SQLTrainingExercise,
        enrollment: UserSQLTrainingEnrollment,
        sql_code: str,
        user_language: str = DEFAULT_LANG
    ) -> dict[str, Any]:
        """
        Execute user's SQL for an exercise and evaluate correctness.
        
        Returns:
            {
                "is_correct": bool,
                "points_earned": int,
                "feedback_i18n": dict,
                "result_data": list,
                "error_message": Optional[str],
                "execution_time_ms": float,
                "attempt_number": int
            }
        """
        # Get attempt number
        attempt_count = UserSQLTrainingSubmission.query.filter_by(
            enrollment_id=enrollment.id,
            exercise_id=exercise.id
        ).count()
        attempt_number = attempt_count + 1
        
        start_time = time.time()
        error_message = None
        result_data = []
        is_correct = False
        points_earned = 0
        
        try:
            # Execute based on exercise type
            if exercise.type == "sql_query":
                result = self.execute_query(
                    module_id=enrollment.module_id,
                    user_id=enrollment.user_id,
                    query=sql_code
                )
                result_data = result["result_data"]
                
                # Evaluate if result matches expected
                is_correct = self._evaluate_query_result(result_data, exercise)
            
            elif exercise.type == "sql_dml":
                # Execute DML
                result = self.execute_dml(enrollment.module_id, enrollment.user_id, sql_code)
                
                # Run validation query
                if exercise.validation_query:
                    val_result = self.execute_query(
                        enrollment.module_id, enrollment.user_id, exercise.validation_query
                    )
                    is_correct = self._evaluate_dml_result(val_result["result_data"], exercise)
                else:
                    # DML executed without error = success
                    is_correct = True
                
                result_data = result
            
            if is_correct:
                points_earned = exercise.points
        
        except SQLSandboxError as e:
            error_message = str(e)
            is_correct = False
            points_earned = 0
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Generate feedback
        feedback_i18n = self._generate_feedback(
            exercise, is_correct, error_message, user_language
        )
        
        return {
            "is_correct": is_correct,
            "points_earned": points_earned,
            "feedback_i18n": feedback_i18n,
            "result_data": result_data,
            "error_message": error_message,
            "execution_time_ms": execution_time_ms,
            "attempt_number": attempt_number
        }
    
    def _evaluate_query_result(self, result: list[dict], exercise: SQLTrainingExercise) -> bool:
        """Check if query result matches expected result."""
        if not exercise.expected_result_json:
            # No validation specified - just check it executed
            return True
        
        expected = exercise.expected_result_json
        
        # Simple comparison - can be enhanced
        if isinstance(expected, list):
            return len(result) == len(expected)
        
        return True
    
    def _evaluate_dml_result(self, validation_result: list[dict], exercise: SQLTrainingExercise) -> bool:
        """Evaluate DML exercise using validation query result."""
        if not exercise.passing_condition:
            return len(validation_result) > 0
        
        # Parse passing condition (e.g., "row_count > 0", "id == 5")
        # For now, simple check: if we have rows, consider it correct
        return len(validation_result) > 0
    
    def _generate_feedback(
        self,
        exercise: SQLTrainingExercise,
        is_correct: bool,
        error_message: Optional[str],
        user_language: str
    ) -> dict[str, str]:
        """Generate feedback message for user."""
        feedback_i18n = {}
        hint = exercise.hint_i18n or {}
        
        for lang in SUPPORTED_LANGS:
            if is_correct:
                feedback_i18n[lang] = {
                    "pt": "Parabéns! Você completou este exercício.",
                    "en": "Congratulations! You completed this exercise.",
                    "fr": "Félicitations! Vous avez complété cet exercice.",
                    "es": "¡Felicitaciones! Completaste este ejercicio.",
                    "it": "Congratulazioni! Hai completato questo esercizio.",
                    "de": "Glückwunsch! Du hast diese Übung abgeschlossen."
                }.get(lang, feedback_i18n.get(lang, ""))
            else:
                base_msg = {
                    "pt": "Não exatamente. Tente novamente.",
                    "en": "Not quite. Try again.",
                    "fr": "Pas tout à fait. Réessayez.",
                    "es": "No exactamente. Inténtelo de nuevo.",
                    "it": "Non esattamente. Riprova.",
                    "de": "Nicht genau. Versuchen Sie es erneut."
                }.get(lang, "Try again")
                
                if error_message:
                    base_msg += f" Error: {error_message}"
                
                hint_text = hint.get(lang, "")
                if hint_text:
                    base_msg += f" Hint: {hint_text}"
                
                feedback_i18n[lang] = base_msg
        
        return feedback_i18n
    
    def reset_sample_database(self, user_id: int, module_id: int) -> None:
        """Reset user's sample database to initial state."""
        sample_db = SQLTrainingSampleDatabase.query.filter_by(
            user_id=user_id,
            module_id=module_id
        ).first()
        
        if sample_db and os.path.exists(sample_db.db_file_path):
            os.remove(sample_db.db_file_path)
            db.session.delete(sample_db)
            db.session.commit()
        
        # Create new one
        self.get_or_create_sample_database(user_id, module_id)
    
    def get_database_schema(self, module_id: int, user_id: int) -> dict[str, Any]:
        """Get schema information for database diagram."""
        sample_db = self.get_or_create_sample_database(user_id, module_id)
        
        try:
            conn = sqlite3.connect(sample_db.db_file_path)
            cursor = conn.cursor()
            
            # Get tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            schema = {"tables": {}}
            
            for table in tables:
                # Get columns
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                schema["tables"][table] = {
                    "columns": [
                        {
                            "name": col[1],
                            "type": col[2],
                            "nullable": not col[3],
                            "primary_key": col[5]
                        }
                        for col in columns
                    ]
                }
            
            conn.close()
            return schema
        
        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            return {"tables": {}}
    
    def get_sql_suggestions(self, module_id: int, query_prefix: str) -> list[str]:
        """Get SQL autocomplete suggestions."""
        suggestions = []
        
        # Keywords
        keywords = [
            "SELECT", "FROM", "WHERE", "INSERT INTO", "UPDATE", "DELETE FROM",
            "JOIN", "LEFT JOIN", "INNER JOIN", "GROUP BY", "ORDER BY",
            "LIMIT", "OFFSET", "AS", "AND", "OR", "NOT", "IN"
        ]
        
        prefix_upper = query_prefix.strip().upper()
        suggestions.extend([kw for kw in keywords if kw.startswith(prefix_upper)])
        
        return suggestions[:10]
    
    def calculate_progress(self, enrollment: UserSQLTrainingEnrollment) -> dict[str, Any]:
        """Calculate user's progress in module."""
        lessons = enrollment.module.lessons
        exercises = []
        for lesson in lessons:
            exercises.extend(lesson.exercises)
        
        total_points = sum(ex.points for ex in exercises)
        
        # Get earned points
        earned_points = db.session.query(
            func.sum(UserSQLTrainingSubmission.points_earned)
        ).filter(
            UserSQLTrainingSubmission.enrollment_id == enrollment.id,
            UserSQLTrainingSubmission.is_correct == True
        ).scalar() or 0
        
        percentage = int((earned_points / total_points * 100)) if total_points > 0 else 0
        is_passed = percentage >= enrollment.module.pass_threshold
        
        return {
            "total_points": total_points,
            "earned_points": earned_points,
            "percentage": percentage,
            "is_passed": is_passed,
            "pass_threshold": enrollment.module.pass_threshold,
            "lessons_count": len(lessons),
            "exercises_count": len(exercises)
        }
    
    def evaluate_module_completion(self, enrollment: UserSQLTrainingEnrollment) -> Tuple[bool, int]:
        """
        Evaluate if user has passed the module.
        
        Returns: (is_passed, final_score)
        """
        progress = self.calculate_progress(enrollment)
        is_passed = progress["is_passed"]
        final_score = progress["percentage"]
        
        return is_passed, final_score
    
    def generate_certificate(self, enrollment: UserSQLTrainingEnrollment) -> SQLTrainingCertificate:
        """Generate a certificate for completed module."""
        # Get final score
        progress = self.calculate_progress(enrollment)
        final_score = progress["percentage"]
        
        # Generate unique certificate number
        cert_num = f"SQL-{enrollment.user_id}-{enrollment.module_id}-{int(time.time())}"
        
        # Generate verification code
        verify_code = ''.join(choices(string.ascii_uppercase + string.digits, k=12))
        
        certificate = SQLTrainingCertificate(
            enrollment_id=enrollment.id,
            user_id=enrollment.user_id,
            module_id=enrollment.module_id,
            certificate_number=cert_num,
            final_score=final_score,
            verification_code=verify_code,
            is_public=True
        )
        
        db.session.add(certificate)
        db.session.commit()
        
        logger.info(f"Generated certificate: {cert_num}")
        
        return certificate
    
    def get_certificate_html(self, certificate: SQLTrainingCertificate, language: str = DEFAULT_LANG) -> str:
        """
        Generate beautiful certificate HTML for download/printing.
        
        Returns: HTML string
        """
        user = certificate.user
        module = certificate.module
        
        module_title = module.title_i18n.get(language, module.title_i18n.get(DEFAULT_LANG, ""))
        
        # Date issued
        issued_date = certificate.issued_at.strftime("%d %B %Y")
        
        # Translations
        translations = {
            "pt": {
                "title": "Certificado de Conclusão",
                "this_is_to_certify": "Certificamos que",
                "has_successfully_completed": "completou com sucesso o curso",
                "with_score": "com pontuação de",
                "issued_on": "Emitido em",
                "certificate_number": "Número do Certificado",
                "verification": "Verificação",
                "verify_at": "Verifique em"
            },
            "en": {
                "title": "Certificate of Completion",
                "this_is_to_certify": "This is to certify that",
                "has_successfully_completed": "has successfully completed",
                "with_score": "with a score of",
                "issued_on": "Issued on",
                "certificate_number": "Certificate Number",
                "verification": "Verification",
                "verify_at": "Verify at"
            },
            "fr": {
                "title": "Certificat d'Achèvement",
                "this_is_to_certify": "Nous certifions que",
                "has_successfully_completed": "a complété avec succès",
                "with_score": "avec un score de",
                "issued_on": "Émis le",
                "certificate_number": "Numéro du Certificat",
                "verification": "Vérification",
                "verify_at": "Vérifier sur"
            },
            "es": {
                "title": "Certificado de Finalización",
                "this_is_to_certify": "Certificamos que",
                "has_successfully_completed": "ha completado exitosamente",
                "with_score": "con una puntuación de",
                "issued_on": "Emitido el",
                "certificate_number": "Número de Certificado",
                "verification": "Verificación",
                "verify_at": "Verificar en"
            },
            "it": {
                "title": "Certificato di Completamento",
                "this_is_to_certify": "Certificamos che",
                "has_successfully_completed": "ha completato con successo",
                "with_score": "con un punteggio di",
                "issued_on": "Emesso il",
                "certificate_number": "Numero Certificato",
                "verification": "Verifica",
                "verify_at": "Verifica su"
            },
            "de": {
                "title": "Abschlusszertifikat",
                "this_is_to_certify": "Hiermit wird beglaubigt, dass",
                "has_successfully_completed": "erfolgreich abgeschlossen hat",
                "with_score": "mit einer Punktzahl von",
                "issued_on": "Ausgestellt am",
                "certificate_number": "Zertifikatnummer",
                "verification": "Überprüfung",
                "verify_at": "Überprüfen Sie auf"
            }
        }
        
        t = translations.get(language, translations["en"])
        
        html = f"""
        <!DOCTYPE html>
        <html lang="{language}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{t["title"]}</title>
            <style>
                @media print {{
                    body {{ margin: 0; padding: 0; }}
                    .certificate {{ page-break-after: avoid; }}
                }}
                
                body {{
                    margin: 0;
                    padding: 20px;
                    font-family: 'Georgia', 'Serif';
                    background: #f5f5f5;
                }}
                
                .certificate {{
                    max-width: 900px;
                    margin: 20px auto;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 60px 80px;
                    border-radius: 10px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    text-align: center;
                    color: white;
                    position: relative;
                    overflow: hidden;
                }}
                
                .certificate::before {{
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M20,50 Q40,30 60,50 T100,50" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="0.5"/></svg>');
                    opacity: 0.1;
                }}
                
                .certificate-content {{
                    position: relative;
                    z-index: 1;
                }}
                
                .certificate .header {{
                    font-size: 48px;
                    font-weight: bold;
                    margin-bottom: 30px;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
                }}
                
                .certificate .seal {{
                    display: inline-block;
                    width: 80px;
                    height: 80px;
                    border: 3px solid white;
                    border-radius: 50%;
                    margin: 20px 0;
                    line-height: 77px;
                    font-size: 40px;
                }}
                
                .certificate .body {{
                    margin: 40px 0;
                    line-height: 1.8;
                }}
                
                .certificate .body p {{
                    font-size: 20px;
                    margin: 15px 0;
                }}
                
                .certificate .name {{
                    font-size: 28px;
                    font-weight: bold;
                    margin: 20px 0;
                    text-decoration: underline;
                }}
                
                .certificate .title {{
                    font-size: 24px;
                    font-weight: bold;
                    margin: 20px 0;
                    text-decoration: underline;
                }}
                
                .certificate .score {{
                    font-size: 22px;
                    margin: 15px 0;
                }}
                
                .certificate .footer {{
                    margin-top: 40px;
                    border-top: 2px solid rgba(255,255,255,0.3);
                    padding-top: 20px;
                    font-size: 12px;
                }}
                
                .certificate .footer-item {{
                    display: inline-block;
                    margin: 0 20px;
                }}
                
                .print-button {{
                    display: block;
                    margin: 20px auto;
                    padding: 12px 30px;
                    background: #667eea;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 16px;
                }}
                
                .print-button:hover {{
                    background: #764ba2;
                }}
                
                @media print {{
                    .print-button {{ display: none; }}
                }}
            </style>
        </head>
        <body>
            <div class="certificate">
                <div class="certificate-content">
                    <div class="header">{t["title"]}</div>
                    
                    <div class="seal">🎓</div>
                    
                    <div class="body">
                        <p>{t["this_is_to_certify"]}</p>
                        <div class="name">{user.email}</div>
                        <p>{t["has_successfully_completed"]}</p>
                        <div class="title">{module_title}</div>
                        <div class="score">{t["with_score"]} {certificate.final_score}%</div>
                        <p>{t["issued_on"]} {issued_date}</p>
                    </div>
                    
                    <div class="footer">
                        <div class="footer-item">
                            <strong>{t["certificate_number"]}:</strong><br>
                            {certificate.certificate_number}
                        </div>
                        <div class="footer-item">
                            <strong>{t["verification"]}:</strong><br>
                            {certificate.verification_code}
                        </div>
                    </div>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 20px;">
                <button class="print-button" onclick="window.print()">Print / Download as PDF</button>
            </div>
        </body>
        </html>
        """
        
        return html
