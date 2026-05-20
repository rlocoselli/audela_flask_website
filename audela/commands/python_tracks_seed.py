"""Seed commands for additional Python learning tracks.

Tracks included:
- Python Fundamentals
- Machine Learning with Python
- Django Web Development
"""

from __future__ import annotations

import click
from flask import Flask

from ..extensions import db
from .python_data_analysis_seed import _seed_python_subject


TRACKS = [
    {
        "label": "Python Fundamentals",
        "subject": {
            "code": "python-fundamentals",
            "name_i18n": {
                "en": "Python Fundamentals",
                "fr": "Fondamentaux Python",
                "pt": "Fundamentos de Python",
            },
            "description_i18n": {
                "en": "Professional foundation track: syntax, data structures, OOP, testing, and automation.",
                "fr": "Parcours fondamental professionnel : syntaxe, structures de données, POO, tests et automatisation.",
                "pt": "Trilha profissional de base: sintaxe, estruturas de dados, POO, testes e automação.",
            },
            "order": 3,
        },
        "modules": [
            {"code": "pyf101", "title": "Python Syntax & Control Flow", "level": "beginner", "topics": ["variables", "conditionals", "loops"], "project": "CLI calculator"},
            {"code": "pyf102", "title": "Data Structures & Functions", "level": "beginner", "topics": ["lists", "dicts", "functions"], "project": "Inventory manager"},
            {"code": "pyf103", "title": "Object-Oriented Python", "level": "beginner", "topics": ["classes", "inheritance", "dunder methods"], "project": "Library system"},
            {"code": "pyf104", "title": "Testing & Packaging", "level": "intermediate", "topics": ["pytest", "mocking", "packaging"], "project": "Reusable utility package"},
        ],
    },
    {
        "label": "Machine Learning with Python",
        "subject": {
            "code": "machine-learning-python",
            "name_i18n": {
                "en": "Machine Learning with Python",
                "fr": "Machine Learning avec Python",
                "pt": "Machine Learning com Python",
            },
            "description_i18n": {
                "en": "Applied ML track: preprocessing, supervised learning, evaluation, and deployment basics.",
                "fr": "Parcours ML appliqué : prétraitement, apprentissage supervisé, évaluation et bases du déploiement.",
                "pt": "Trilha de ML aplicada: pré-processamento, aprendizado supervisionado, avaliação e noções de deploy.",
            },
            "order": 4,
        },
        "modules": [
            {"code": "mlp101", "title": "ML Workflow & Data Preparation", "level": "beginner", "topics": ["feature engineering", "train/test split", "pipelines"], "project": "Churn dataset preparation"},
            {"code": "mlp102", "title": "Regression Models", "level": "intermediate", "topics": ["linear regression", "regularization", "metrics"], "project": "Price prediction model"},
            {"code": "mlp103", "title": "Classification Models", "level": "intermediate", "topics": ["logistic regression", "trees", "ROC-AUC"], "project": "Fraud classifier"},
            {"code": "mlp104", "title": "Model Tuning & Deployment", "level": "intermediate", "topics": ["grid search", "cross validation", "model serving"], "project": "FastAPI prediction endpoint"},
        ],
    },
    {
        "label": "Django Web Development",
        "subject": {
            "code": "django-web-development",
            "name_i18n": {
                "en": "Django Web Development",
                "fr": "Développement Web Django",
                "pt": "Desenvolvimento Web com Django",
            },
            "description_i18n": {
                "en": "Production-ready Django track: models, views, auth, APIs, and deployment best practices.",
                "fr": "Parcours Django prêt pour la production : modèles, vues, auth, APIs et déploiement.",
                "pt": "Trilha Django pronta para produção: modelos, views, auth, APIs e deploy.",
            },
            "order": 5,
        },
        "modules": [
            {"code": "dj101", "title": "Django Project Foundations", "level": "beginner", "topics": ["apps", "urls", "settings"], "project": "Project skeleton setup"},
            {"code": "dj102", "title": "Models, ORM & Admin", "level": "beginner", "topics": ["models", "migrations", "admin"], "project": "Blog data model"},
            {"code": "dj103", "title": "Views, Templates & Forms", "level": "intermediate", "topics": ["CBV", "template tags", "form validation"], "project": "Ticket submission app"},
            {"code": "dj104", "title": "Auth, APIs & Deployment", "level": "intermediate", "topics": ["authentication", "DRF basics", "gunicorn/nginx"], "project": "JWT-enabled API"},
        ],
    },
]


def _module_quiz_questions(module_title: str, topics: list[str]) -> list[dict]:
    t1 = topics[0] if topics else "core concepts"
    t2 = topics[1] if len(topics) > 1 else "best practices"
    return [
        {
            "text_i18n": {"en": f"What is the main learning objective of '{module_title}'?"},
            "options": [
                ("Mastering practical implementation of the module topics", True),
                ("Only memorizing syntax", False),
                ("Avoiding hands-on exercises", False),
                ("Ignoring debugging and testing", False),
            ],
            "explanation_i18n": {"en": "Each module is designed around practical, project-based outcomes."},
        },
        {
            "text_i18n": {"en": f"Which area is covered in this module: {t1}?"},
            "options": [("Yes, it is a core topic", True), ("No, unrelated", False), ("Only optional", False), ("Deprecated only", False)],
            "explanation_i18n": {"en": "The quiz checks understanding of core module topics."},
        },
        {
            "text_i18n": {"en": f"Why are exercises around '{t2}' important?"},
            "options": [
                ("They build real-world problem-solving skills", True),
                ("They are purely theoretical", False),
                ("They replace all documentation", False),
                ("They avoid collaboration", False),
            ],
            "explanation_i18n": {"en": "Applied practice is central to retention and job readiness."},
        },
        {
            "text_i18n": {"en": "What is the best approach after completing a lesson?"},
            "options": [
                ("Practice with exercises and review quiz feedback", True),
                ("Skip exercises and continue", False),
                ("Retype examples without understanding", False),
                ("Disable tests", False),
            ],
            "explanation_i18n": {"en": "Combining practice with feedback closes learning gaps."},
        },
        {
            "text_i18n": {"en": "What indicates module mastery?"},
            "options": [
                ("Passing quizzes and completing practical tasks", True),
                ("Reading titles only", False),
                ("Avoiding projects", False),
                ("Ignoring errors", False),
            ],
            "explanation_i18n": {"en": "Mastery requires demonstrated understanding and implementation."},
        },
    ]


def _seed_track(track: dict, force: bool = False) -> dict:
    from ..models.e_learning import (
        ELearningExercise,
        ELearningLesson,
        ELearningModule,
        ELearningQuiz,
        ELearningQuizOption,
        ELearningQuizQuestion,
        ELearningSubject,
    )

    stats = {"subjects": 0, "modules": 0, "lessons": 0, "exercises": 0, "quizzes": 0, "questions": 0}
    subject_def = track["subject"]

    subject = ELearningSubject.query.filter_by(code=subject_def["code"]).first()
    if not subject:
        subject = ELearningSubject(code=subject_def["code"])
        db.session.add(subject)
        stats["subjects"] += 1

    subject.name_i18n = subject_def["name_i18n"]
    subject.description_i18n = subject_def["description_i18n"]
    subject.icon_url = "/static/assets/icons/analytics.svg"
    subject.order = subject_def["order"]
    subject.is_active = True
    db.session.flush()

    for module_index, module_def in enumerate(track["modules"], start=1):
        module = ELearningModule.query.filter_by(subject_id=subject.id, code=module_def["code"]).first()
        if not module:
            module = ELearningModule(subject_id=subject.id, code=module_def["code"])
            db.session.add(module)
            stats["modules"] += 1
        elif not force:
            pass

        module.title_i18n = {"en": module_def["title"], "fr": module_def["title"], "pt": module_def["title"]}
        module.description_i18n = {
            "en": (
                f"{module_def['title']} with concept breakdowns, production examples, coding labs, "
                "and a mini-project connected to real engineering workflows."
            ),
            "fr": (
                f"{module_def['title']} avec explication des concepts, exemples reel production, "
                "labs de code et mini-projet relie aux workflows d ingenierie."
            ),
            "pt": (
                f"{module_def['title']} com explicação de conceitos, exemplos reais de produção, "
                "labs de código e mini-projeto conectado a fluxos de engenharia."
            ),
        }
        module.level = module_def["level"]
        module.total_lessons = 2
        module.total_exercises = 4
        module.pass_threshold = 70
        module.points_on_completion = 60 + (module_index * 10)
        module.estimated_hours = 2.0
        module.order = module_index
        module.is_active = True
        module.sample_database_schema = None
        module.sample_data_sql = None
        db.session.flush()

        quiz_questions = _module_quiz_questions(module_def["title"], module_def.get("topics", []))

        for lesson_index in range(1, 3):
            lesson_code = f"{module_def['code']}-les{lesson_index}"
            lesson = ELearningLesson.query.filter_by(module_id=module.id, code=lesson_code).first()
            if not lesson:
                lesson = ELearningLesson(module_id=module.id, code=lesson_code)
                db.session.add(lesson)
                stats["lessons"] += 1

            lesson_title = f"{module_def['title']} – {'Guided Lesson' if lesson_index == 1 else 'Hands-On Lab'}"
            lesson.title_i18n = {"en": lesson_title, "fr": lesson_title, "pt": lesson_title}
            lesson.description_i18n = {
                "en": (
                    f"Real implementation focus on: {', '.join(module_def.get('topics', []))}. "
                    f"Includes a concrete use case for '{module_def.get('project', 'capstone')}'."
                ),
                "fr": (
                    f"Focus implementation reelle: {', '.join(module_def.get('topics', []))}. "
                    f"Inclut un cas concret pour '{module_def.get('project', 'capstone')}'."
                ),
                "pt": (
                    f"Foco em implementação real: {', '.join(module_def.get('topics', []))}. "
                    f"Inclui um caso concreto para '{module_def.get('project', 'capstone')}'."
                ),
            }
            real_example = (
                "Example: validate user payload, normalize data, and return deterministic output for API consumers."
                if lesson_index == 1
                else "Example: implement automated checks with asserts/pytest style tests before release."
            )
            lesson.content_html_i18n = {
                "en": (
                    f"<h3>{lesson_title}</h3>"
                    f"<p>Focus topics: {', '.join(module_def.get('topics', []))}.</p>"
                    "<p>Concept briefing: choose readable abstractions first, then optimize with profiling data.</p>"
                    f"<p><strong>Real example:</strong> {real_example}</p>"
                    f"<p>Mini-project: <strong>{module_def.get('project', 'Capstone task')}</strong></p>"
                )
            }
            lesson.key_concepts_i18n = {
                "en": [
                    f"{module_def['title']} practical architecture",
                    "Readable implementation before micro-optimization",
                    "Testing strategy and regression prevention",
                    "Operational readiness for production handoff",
                ],
                "fr": [
                    f"Architecture pratique: {module_def['title']}",
                    "Implementation lisible avant micro-optimisation",
                    "Strategie de test et prevention des regressions",
                    "Readiness operationnelle avant mise en prod",
                ],
            }
            lesson.order = lesson_index
            lesson.is_active = True
            db.session.flush()

            for exercise_index in range(1, 3):
                exercise_code = f"{module_def['code']}-les{lesson_index}-ex{exercise_index}"
                exercise = ELearningExercise.query.filter_by(lesson_id=lesson.id, code=exercise_code).first()
                if not exercise:
                    exercise = ELearningExercise(lesson_id=lesson.id, code=exercise_code)
                    db.session.add(exercise)
                    stats["exercises"] += 1

                exercise.title_i18n = {
                    "en": f"{module_def['title']} – {'Core Exercise' if exercise_index == 1 else 'Applied Exercise'}"
                }
                exercise.instruction_i18n = {
                    "en": f"Implement a practical task using: {', '.join(module_def.get('topics', []))}."
                }
                exercise.type = "code_challenge"
                exercise.expected_sql = "# Write your Python solution here"
                exercise.hint_i18n = {
                    "en": [
                        "Break down the task into small functions.",
                        "Run tests or sample inputs before submitting.",
                    ]
                }
                exercise.points = 25 + (exercise_index * 5)
                exercise.order = exercise_index
                exercise.is_active = True
                db.session.flush()

            quiz_code = f"{module_def['code']}-les{lesson_index}-quiz"
            quiz = ELearningQuiz.query.filter_by(lesson_id=lesson.id, code=quiz_code).first()
            if not quiz:
                quiz = ELearningQuiz(lesson_id=lesson.id, code=quiz_code)
                db.session.add(quiz)
                stats["quizzes"] += 1

            quiz.title_i18n = {"en": f"{module_def['title']} – Knowledge Check"}
            quiz.description_i18n = {"en": "Quiz for key concepts from this lesson."}
            quiz.time_limit_minutes = 10
            quiz.pass_threshold = 70
            quiz.max_attempts = None
            quiz.shuffle_questions = True
            quiz.show_correct_answers = True
            quiz.points_on_pass = 25
            quiz.order = lesson_index
            quiz.is_active = True
            db.session.flush()

            for question_index, question_def in enumerate(quiz_questions, start=1):
                question = ELearningQuizQuestion.query.filter_by(quiz_id=quiz.id, order=question_index).first()
                if not question:
                    question = ELearningQuizQuestion(quiz_id=quiz.id)
                    db.session.add(question)
                    stats["questions"] += 1

                question.order = question_index
                question.question_type = "multiple_choice"
                question.text_i18n = question_def["text_i18n"]
                question.explanation_i18n = question_def.get("explanation_i18n", {})
                question.points = 1
                question.allow_partial_credit = False
                question.penalty_points = 0
                question.is_active = True
                db.session.flush()

                for option_index, (option_text, is_correct) in enumerate(question_def["options"], start=1):
                    option = ELearningQuizOption.query.filter_by(question_id=question.id, order=option_index).first()
                    if not option:
                        option = ELearningQuizOption(question_id=question.id)
                        db.session.add(option)

                    option.order = option_index
                    option.text_i18n = {"en": option_text}
                    option.is_correct = bool(is_correct)
                    db.session.flush()

    db.session.commit()
    return stats


def init_python_tracks_seed_cli(app: Flask) -> None:
    """Register seed commands for Python tracks."""

    @app.cli.command("seed-python-fundamentals")
    @click.option("--force", is_flag=True, default=False, help="Re-seed / update existing records")
    def seed_python_fundamentals(force: bool):
        click.echo("🐍 Seeding Python Fundamentals track...")
        stats = _seed_track(TRACKS[0], force=force)
        click.echo(f"  ✅ Subjects  : {stats['subjects']}")
        click.echo(f"  ✅ Modules   : {stats['modules']}")
        click.echo(f"  ✅ Lessons   : {stats['lessons']}")
        click.echo(f"  ✅ Exercises : {stats['exercises']}")
        click.echo(f"  ✅ Quizzes   : {stats['quizzes']}")
        click.echo(f"  ✅ Questions : {stats['questions']}")

    @app.cli.command("seed-machine-learning")
    @click.option("--force", is_flag=True, default=False, help="Re-seed / update existing records")
    def seed_machine_learning(force: bool):
        click.echo("🤖 Seeding Machine Learning track...")
        stats = _seed_track(TRACKS[1], force=force)
        click.echo(f"  ✅ Subjects  : {stats['subjects']}")
        click.echo(f"  ✅ Modules   : {stats['modules']}")
        click.echo(f"  ✅ Lessons   : {stats['lessons']}")
        click.echo(f"  ✅ Exercises : {stats['exercises']}")
        click.echo(f"  ✅ Quizzes   : {stats['quizzes']}")
        click.echo(f"  ✅ Questions : {stats['questions']}")

    @app.cli.command("seed-python-django")
    @click.option("--force", is_flag=True, default=False, help="Re-seed / update existing records")
    def seed_python_django(force: bool):
        click.echo("🌐 Seeding Django Web Development track...")
        stats = _seed_track(TRACKS[2], force=force)
        click.echo(f"  ✅ Subjects  : {stats['subjects']}")
        click.echo(f"  ✅ Modules   : {stats['modules']}")
        click.echo(f"  ✅ Lessons   : {stats['lessons']}")
        click.echo(f"  ✅ Exercises : {stats['exercises']}")
        click.echo(f"  ✅ Quizzes   : {stats['quizzes']}")
        click.echo(f"  ✅ Questions : {stats['questions']}")

    @app.cli.command("seed-python-tracks")
    @click.option("--force", is_flag=True, default=False, help="Re-seed / update existing records")
    def seed_python_tracks(force: bool):
        click.echo("🚀 Seeding all Python tracks (fundamentals + data analysis + ML + Django)...")
        totals = {"subjects": 0, "modules": 0, "lessons": 0, "exercises": 0, "quizzes": 0, "questions": 0}

        for track in TRACKS:
            click.echo(f"\n• {track['label']}")
            stats = _seed_track(track, force=force)
            for key in totals:
                totals[key] += stats[key]
            click.echo(f"  modules={stats['modules']} lessons={stats['lessons']} exercises={stats['exercises']} quizzes={stats['quizzes']} questions={stats['questions']}")

        click.echo("\n• Python Data Analysis")
        pda_stats = _seed_python_subject(force=force)
        for key in totals:
            totals[key] += pda_stats[key]
        click.echo(f"  modules={pda_stats['modules']} lessons={pda_stats['lessons']} exercises={pda_stats['exercises']} quizzes={pda_stats['quizzes']} questions={pda_stats['questions']}")

        click.echo("\n✅ All Python tracks seeded.")
        click.echo(f"  Subjects  : {totals['subjects']}")
        click.echo(f"  Modules   : {totals['modules']}")
        click.echo(f"  Lessons   : {totals['lessons']}")
        click.echo(f"  Exercises : {totals['exercises']}")
        click.echo(f"  Quizzes   : {totals['quizzes']}")
        click.echo(f"  Questions : {totals['questions']}")