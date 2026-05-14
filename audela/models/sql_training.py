"""
SQL Training Module Models

Free SQL training with modules, lessons, exercises, and certificates.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import UniqueConstraint

from ..extensions import db


class SQLTrainingModule(db.Model):
    """SQL Training Module - Top level course content."""
    
    __tablename__ = "sql_training_modules"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), nullable=False, unique=True, index=True)  # sql_101, sql_intermediate, etc.
    
    # Internationalized content (JSON keys per language)
    title_i18n = db.Column(db.JSON, nullable=False, default=dict)  # {"pt": "SQL 101", "en": "SQL 101", ...}
    description_i18n = db.Column(db.JSON, nullable=False, default=dict)
    
    # Module metadata
    level = db.Column(db.String(32), nullable=False, default="beginner")  # beginner, intermediate, advanced
    order = db.Column(db.Integer, nullable=False, default=0)  # Display order
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    # Sample database setup
    sample_database_schema = db.Column(db.Text, nullable=True)  # SQL DDL for creating sample database
    sample_data_sql = db.Column(db.Text, nullable=True)  # SQL for inserting sample data
    
    # Module stats
    total_lessons = db.Column(db.Integer, nullable=False, default=0)
    total_exercises = db.Column(db.Integer, nullable=False, default=0)
    estimated_hours = db.Column(db.Float, nullable=False, default=2.0)
    
    # Pass requirement
    pass_threshold = db.Column(db.Integer, nullable=False, default=80)  # Minimum % to pass
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lessons = db.relationship("SQLTrainingLesson", back_populates="module", cascade="all, delete-orphan")
    enrollments = db.relationship("UserSQLTrainingEnrollment", back_populates="module", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SQLTrainingModule {self.code}>"


class SQLTrainingLesson(db.Model):
    """Individual lesson within a module."""
    
    __tablename__ = "sql_training_lessons"

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("sql_training_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    
    code = db.Column(db.String(64), nullable=False, index=True)
    order = db.Column(db.Integer, nullable=False, default=0)
    
    # Internationalized content
    title_i18n = db.Column(db.JSON, nullable=False, default=dict)
    description_i18n = db.Column(db.JSON, nullable=False, default=dict)
    
    # Lesson content
    content_html_i18n = db.Column(db.JSON, nullable=True)  # HTML content with images/examples per language
    key_concepts_i18n = db.Column(db.JSON, nullable=True)  # JSON list of key concepts
    
    # Resources
    example_sql_i18n = db.Column(db.JSON, nullable=True)  # SQL examples per language
    images_urls = db.Column(db.JSON, nullable=True)  # List of image URLs
    
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("module_id", "code", name="uq_lesson_code_per_module"),
    )

    # Relationships
    module = db.relationship("SQLTrainingModule", back_populates="lessons")
    exercises = db.relationship("SQLTrainingExercise", back_populates="lesson", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SQLTrainingLesson {self.code}>"


class SQLTrainingExercise(db.Model):
    """Exercise within a lesson (theory + practice)."""
    
    __tablename__ = "sql_training_exercises"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("sql_training_lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    
    code = db.Column(db.String(64), nullable=False, index=True)
    order = db.Column(db.Integer, nullable=False, default=0)
    
    # Exercise type
    type = db.Column(db.String(32), nullable=False, default="sql_dml")  # sql_dml, sql_query, manual
    
    # Internationalized content
    title_i18n = db.Column(db.JSON, nullable=False, default=dict)
    instruction_i18n = db.Column(db.JSON, nullable=False, default=dict)
    hint_i18n = db.Column(db.JSON, nullable=True)
    
    # Expected solution(s) - multiple solutions allowed
    expected_sql = db.Column(db.Text, nullable=True)  # For query exercises
    expected_result_json = db.Column(db.JSON, nullable=True)  # Expected result set
    
    # For DML exercises: INSERT, UPDATE, DELETE
    dml_operation = db.Column(db.String(32), nullable=True)  # INSERT, UPDATE, DELETE
    
    # Validation
    validation_query = db.Column(db.Text, nullable=True)  # Query to validate exercise
    passing_condition = db.Column(db.String(255), nullable=True)  # How to determine if exercise passed
    
    points = db.Column(db.Integer, nullable=False, default=10)
    
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("lesson_id", "code", name="uq_exercise_code_per_lesson"),
    )

    # Relationships
    lesson = db.relationship("SQLTrainingLesson", back_populates="exercises")
    submissions = db.relationship("UserSQLTrainingSubmission", back_populates="exercise", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SQLTrainingExercise {self.code}>"


class UserSQLTrainingEnrollment(db.Model):
    """User enrollment in a SQL training module."""
    
    __tablename__ = "user_sql_training_enrollments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("sql_training_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Progress
    status = db.Column(db.String(32), nullable=False, default="enrolled")  # enrolled, in_progress, completed, paused
    progress_percentage = db.Column(db.Integer, nullable=False, default=0)
    
    # Scores
    overall_score = db.Column(db.Integer, nullable=False, default=0)
    passed = db.Column(db.Boolean, nullable=False, default=False)
    
    # Dates
    enrolled_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Lesson progress - JSON tracking which lessons/exercises are done
    lessons_progress_json = db.Column(db.JSON, nullable=False, default=dict)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "module_id", name="uq_user_enrollment_per_module"),
    )

    # Relationships
    user = db.relationship("User")
    module = db.relationship("SQLTrainingModule", back_populates="enrollments")
    submissions = db.relationship("UserSQLTrainingSubmission", back_populates="enrollment")

    def __repr__(self):
        return f"<UserSQLTrainingEnrollment user={self.user_id} module={self.module_id}>"


class UserSQLTrainingSubmission(db.Model):
    """User submission for an exercise."""
    
    __tablename__ = "user_sql_training_submissions"

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("user_sql_training_enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey("sql_training_exercises.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Submission content
    submitted_sql = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Evaluation
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    points_earned = db.Column(db.Integer, nullable=False, default=0)
    feedback_i18n = db.Column(db.JSON, nullable=True)  # Feedback per language
    result_json = db.Column(db.JSON, nullable=True)  # Query execution result
    
    # Execution info
    execution_time_ms = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # Attempt tracking
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    enrollment = db.relationship("UserSQLTrainingEnrollment", back_populates="submissions")
    exercise = db.relationship("SQLTrainingExercise", back_populates="submissions")
    user = db.relationship("User")

    def __repr__(self):
        return f"<UserSQLTrainingSubmission user={self.user_id} exercise={self.exercise_id}>"


class SQLTrainingCertificate(db.Model):
    """Certificate issued upon module completion."""
    
    __tablename__ = "sql_training_certificates"

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("user_sql_training_enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("sql_training_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Certificate details
    certificate_number = db.Column(db.String(64), nullable=False, unique=True, index=True)  # Unique ID for certificate
    final_score = db.Column(db.Integer, nullable=False)
    
    # Certificate validity
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # Optional expiry
    
    # Sharing/verification
    verification_code = db.Column(db.String(32), nullable=False, unique=True, index=True)  # For public verification
    is_public = db.Column(db.Boolean, nullable=False, default=True)  # Shareable on LinkedIn
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = db.relationship("User")
    module = db.relationship("SQLTrainingModule")
    enrollment = db.relationship("UserSQLTrainingEnrollment")

    def __repr__(self):
        return f"<SQLTrainingCertificate {self.certificate_number}>"


class SQLTrainingSampleDatabase(db.Model):
    """Sandbox databases for training - one per module per user session."""
    
    __tablename__ = "sql_training_sample_databases"

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("sql_training_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # SQLite database per user+module (file-based)
    db_file_path = db.Column(db.String(512), nullable=True)  # Path to SQLite database file
    
    # Alternative: in-memory state (JSON representation)
    schema_state_json = db.Column(db.JSON, nullable=True)  # Tables, columns, constraints
    data_state_json = db.Column(db.JSON, nullable=True)  # Current data state
    
    # Status
    is_initialized = db.Column(db.Boolean, nullable=False, default=False)
    last_reset_at = db.Column(db.DateTime, nullable=True)
    
    # Expiry - clean up old databases
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(days=30))
    
    __table_args__ = (
        UniqueConstraint("module_id", "user_id", name="uq_sample_db_per_user_module"),
    )

    # Relationships
    module = db.relationship("SQLTrainingModule")
    user = db.relationship("User")

    def __repr__(self):
        return f"<SQLTrainingSampleDatabase user={self.user_id} module={self.module_id}>"
