"""
E-Learning Platform Models

Multi-subject learning platform with gamification (achievements, points, leaderboards).
Replaces: sql_training.py (generic multi-subject version)
Supports: SQL, Python, Machine Learning, etc.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import UniqueConstraint

from ..extensions import db


class ELearningSubject(db.Model):
    """Subject category (SQL, Python, Machine Learning, etc.)."""
    
    __tablename__ = "e_learning_subjects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), nullable=False, unique=True, index=True)  # sql, python, ml, excel
    
    # Internationalized metadata
    name_i18n = db.Column(db.JSON, nullable=False, default=dict)  # {"pt": "SQL", "en": "SQL", ...}
    description_i18n = db.Column(db.JSON, nullable=False, default=dict)
    icon_url = db.Column(db.String(255), nullable=True)  # /assets/icons/sql.svg
    
    order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    modules = db.relationship("ELearningModule", back_populates="subject", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ELearningSubject {self.code}>"


class ELearningModule(db.Model):
    """Learning module within a subject (e.g., "SQL 101" is a module in SQL subject)."""
    
    __tablename__ = "e_learning_modules"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("e_learning_subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    code = db.Column(db.String(64), nullable=False, index=True)  # sql_101, sql_intermediate, etc
    
    # Internationalized content
    title_i18n = db.Column(db.JSON, nullable=False, default=dict)
    description_i18n = db.Column(db.JSON, nullable=False, default=dict)
    
    # Module metadata
    level = db.Column(db.String(32), nullable=False, default="beginner")  # beginner, intermediate, advanced
    order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    # Sample database setup (for SQL/DB subjects)
    sample_database_schema = db.Column(db.Text, nullable=True)
    sample_data_sql = db.Column(db.Text, nullable=True)
    
    # Stats
    total_lessons = db.Column(db.Integer, nullable=False, default=0)
    total_exercises = db.Column(db.Integer, nullable=False, default=0)
    estimated_hours = db.Column(db.Float, nullable=False, default=2.0)
    
    # Pass requirement
    pass_threshold = db.Column(db.Integer, nullable=False, default=80)
    
    # Gamification rewards
    points_on_completion = db.Column(db.Integer, nullable=False, default=100)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("subject_id", "code", name="uq_module_code_per_subject"),
    )

    # Relationships
    subject = db.relationship("ELearningSubject", back_populates="modules")
    lessons = db.relationship("ELearningLesson", back_populates="module", cascade="all, delete-orphan")
    enrollments = db.relationship("UserELearningEnrollment", back_populates="module", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ELearningModule {self.code}>"


class ELearningLesson(db.Model):
    """Individual lesson within a module."""
    
    __tablename__ = "e_learning_lessons"

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("e_learning_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    
    code = db.Column(db.String(64), nullable=False, index=True)
    order = db.Column(db.Integer, nullable=False, default=0)
    
    # Internationalized content
    title_i18n = db.Column(db.JSON, nullable=False, default=dict)
    description_i18n = db.Column(db.JSON, nullable=False, default=dict)
    
    # Lesson content
    content_html_i18n = db.Column(db.JSON, nullable=True)  # HTML with images/examples per language
    key_concepts_i18n = db.Column(db.JSON, nullable=True)  # JSON list of concepts
    example_sql_i18n = db.Column(db.JSON, nullable=True)  # Code examples per language
    images_urls = db.Column(db.JSON, nullable=True)  # Image URLs
    
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("module_id", "code", name="uq_lesson_code_per_module"),
    )

    # Relationships
    module = db.relationship("ELearningModule", back_populates="lessons")
    exercises = db.relationship("ELearningExercise", back_populates="lesson", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ELearningLesson {self.code}>"


class ELearningExercise(db.Model):
    """Exercise within a lesson."""
    
    __tablename__ = "e_learning_exercises"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("e_learning_lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    
    code = db.Column(db.String(64), nullable=False, index=True)
    order = db.Column(db.Integer, nullable=False, default=0)
    
    # Exercise type
    type = db.Column(db.String(32), nullable=False, default="sql_dml")  # sql_dml, sql_query, code, multiple_choice, etc.
    
    # Internationalized content
    title_i18n = db.Column(db.JSON, nullable=False, default=dict)
    instruction_i18n = db.Column(db.JSON, nullable=False, default=dict)
    hint_i18n = db.Column(db.JSON, nullable=True)
    
    # Expected solution(s)
    expected_sql = db.Column(db.Text, nullable=True)
    expected_result_json = db.Column(db.JSON, nullable=True)
    
    # DML operations: INSERT, UPDATE, DELETE
    dml_operation = db.Column(db.String(32), nullable=True)
    
    # Validation
    validation_query = db.Column(db.Text, nullable=True)
    passing_condition = db.Column(db.String(255), nullable=True)
    
    # Gamification
    points = db.Column(db.Integer, nullable=False, default=10)
    
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("lesson_id", "code", name="uq_exercise_code_per_lesson"),
    )

    # Relationships
    lesson = db.relationship("ELearningLesson", back_populates="exercises")
    submissions = db.relationship("UserELearningSubmission", back_populates="exercise", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ELearningExercise {self.code}>"


class UserELearningProfile(db.Model):
    """User's gamification profile across all subjects."""
    
    __tablename__ = "user_e_learning_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Gamification stats
    total_points = db.Column(db.Integer, nullable=False, default=0)  # Total points accrued
    current_level = db.Column(db.Integer, nullable=False, default=1)  # Level 1, 2, 3, etc. (100 points per level)
    current_streak = db.Column(db.Integer, nullable=False, default=0)  # Days in a row
    longest_streak = db.Column(db.Integer, nullable=False, default=0)  # Highest streak
    
    # Activity tracking
    modules_completed = db.Column(db.Integer, nullable=False, default=0)
    exercises_completed = db.Column(db.Integer, nullable=False, default=0)
    total_study_hours = db.Column(db.Float, nullable=False, default=0.0)
    
    # Last activity
    last_activity_at = db.Column(db.DateTime, nullable=True)
    last_streak_date = db.Column(db.Date, nullable=True)  # Last date in streak
    
    # Preferences
    preferred_language = db.Column(db.String(8), nullable=False, default="pt")
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship("User")
    achievements = db.relationship("UserAchievement", back_populates="profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserELearningProfile user={self.user_id} level={self.current_level} points={self.total_points}>"


class Achievement(db.Model):
    """Achievement/Badge definitions (system-wide)."""
    
    __tablename__ = "e_learning_achievements"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), nullable=False, unique=True, index=True)  # first_lesson, perfect_score, etc.
    
    # Metadata
    name_i18n = db.Column(db.JSON, nullable=False, default=dict)  # {"pt": "Primeiro Exercício", ...}
    description_i18n = db.Column(db.JSON, nullable=False, default=dict)
    icon_url = db.Column(db.String(255), nullable=True)  # /assets/badges/first_lesson.svg
    
    # Achievement type
    category = db.Column(db.String(32), nullable=False, default="general")  # general, subject_specific, milestone
    
    # Reward
    points_reward = db.Column(db.Integer, nullable=False, default=10)
    
    # Properties
    rarity = db.Column(db.String(32), nullable=False, default="common")  # common, uncommon, rare, epic, legendary
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users_with_achievement = db.relationship("UserAchievement", back_populates="achievement", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Achievement {self.code}>"


class UserAchievement(db.Model):
    """User's earned achievements/badges."""
    
    __tablename__ = "user_e_learning_achievements"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("user_e_learning_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey("e_learning_achievements.id", ondelete="CASCADE"), nullable=False, index=True)
    
    earned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("profile_id", "achievement_id", name="uq_user_achievement_once"),
    )

    # Relationships
    profile = db.relationship("UserELearningProfile", back_populates="achievements")
    achievement = db.relationship("Achievement", back_populates="users_with_achievement")

    def __repr__(self):
        return f"<UserAchievement achievement={self.achievement_id}>"


class UserELearningEnrollment(db.Model):
    """User enrollment in a learning module."""
    
    __tablename__ = "user_e_learning_enrollments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("e_learning_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Progress
    status = db.Column(db.String(32), nullable=False, default="enrolled")  # enrolled, in_progress, completed, paused
    progress_percentage = db.Column(db.Integer, nullable=False, default=0)
    
    # Scores
    overall_score = db.Column(db.Integer, nullable=False, default=0)
    passed = db.Column(db.Boolean, nullable=False, default=False)
    
    # Learning time
    time_spent_minutes = db.Column(db.Integer, nullable=False, default=0)
    
    # Dates
    enrolled_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Progress tracking
    lessons_progress_json = db.Column(db.JSON, nullable=False, default=dict)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "module_id", name="uq_user_enrollment_per_module"),
    )

    # Relationships
    user = db.relationship("User")
    module = db.relationship("ELearningModule", back_populates="enrollments")
    submissions = db.relationship("UserELearningSubmission", back_populates="enrollment")
    certificate = db.relationship("ELearningCertificate", back_populates="enrollment", uselist=False)

    def __repr__(self):
        return f"<UserELearningEnrollment user={self.user_id} module={self.module_id}>"


class UserELearningSubmission(db.Model):
    """User submission for an exercise."""
    
    __tablename__ = "user_e_learning_submissions"

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("user_e_learning_enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey("e_learning_exercises.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Submission
    submitted_sql = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Evaluation
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    points_earned = db.Column(db.Integer, nullable=False, default=0)
    feedback_i18n = db.Column(db.JSON, nullable=True)
    result_json = db.Column(db.JSON, nullable=True)
    
    # Execution
    execution_time_ms = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # Tracking
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    enrollment = db.relationship("UserELearningEnrollment", back_populates="submissions")
    exercise = db.relationship("ELearningExercise", back_populates="submissions")
    user = db.relationship("User")

    def __repr__(self):
        return f"<UserELearningSubmission user={self.user_id} exercise={self.exercise_id}>"


class ELearningCertificate(db.Model):
    """Certificate issued upon module completion."""
    
    __tablename__ = "e_learning_certificates"

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("user_e_learning_enrollments.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("e_learning_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Certificate metadata
    certificate_number = db.Column(db.String(64), nullable=False, unique=True, index=True)
    final_score = db.Column(db.Integer, nullable=False)
    
    # Validity
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Sharing & verification
    verification_code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    is_public = db.Column(db.Boolean, nullable=False, default=True)
    viewed_count = db.Column(db.Integer, nullable=False, default=0)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = db.relationship("User")
    module = db.relationship("ELearningModule")
    enrollment = db.relationship("UserELearningEnrollment", back_populates="certificate")

    def __repr__(self):
        return f"<ELearningCertificate {self.certificate_number}>"


class ELearningSampleDatabase(db.Model):
    """Sandbox databases for training (one per module per user)."""
    
    __tablename__ = "e_learning_sample_databases"

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("e_learning_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Database state
    db_file_path = db.Column(db.String(512), nullable=True)  # SQLite file path
    
    # Status
    is_initialized = db.Column(db.Boolean, nullable=False, default=False)
    last_reset_at = db.Column(db.DateTime, nullable=True)
    
    # Lifecycle
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(days=30))
    
    __table_args__ = (
        UniqueConstraint("module_id", "user_id", name="uq_sample_db_per_user_module"),
    )

    # Relationships
    module = db.relationship("ELearningModule")
    user = db.relationship("User")

    def __repr__(self):
        return f"<ELearningSampleDatabase user={self.user_id} module={self.module_id}>"
