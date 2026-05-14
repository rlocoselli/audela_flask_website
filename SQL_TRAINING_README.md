# SQL Training Module - Complete Feature

A free, multi-language SQL training platform built into AUDELA, featuring interactive exercises, real-time SQL execution, beautiful certificates, and progress tracking.

## Features

### ✨ Core Features

- **🎓 Free SQL Training**: Beginner, Intermediate, and Advanced modules
- **💻 Interactive SQL Editor**: Write and execute SQL with real-time feedback
- **🔄 DML Exercises**: INSERT, UPDATE, DELETE practice with validation
- **🗄️ Sample Databases**: Pre-populated databases for each module
- **📊 Database Diagrams**: Visual schema representation with D3.js
- **🎯 Progress Tracking**: Real-time progress bars and score tracking
- **🏆 Beautiful Certificates**: LinkedIn-shareable certificates with verification codes
- **🌍 Multi-Language Support**: Portuguese, English, French, Spanish, Italian, German
- **📱 Responsive Design**: Works on desktop, tablet, and mobile
- **🚀 SQL Sandbox**: Secure, isolated SQLite sandbox for each user+module

## Architecture

```
SQL Training Module
├── Models (audela/models/sql_training.py)
│   ├── SQLTrainingModule
│   ├── SQLTrainingLesson
│   ├── SQLTrainingExercise
│   ├── UserSQLTrainingEnrollment
│   ├── UserSQLTrainingSubmission
│   ├── SQLTrainingCertificate
│   └── SQLTrainingSampleDatabase
├── Routes (audela/blueprints/sql_training/)
│   ├── routes.py (UI routes)
│   ├── api_routes.py (API endpoints)
│   └── __init__.py (Blueprint registration)
├── Services (audela/services/sql_training_service.py)
│   └── SQLTrainingService (SQL execution, evaluation, certificates)
├── Templates (templates/sql_training/)
│   ├── base_sql_training.html
│   ├── modules_list.html
│   ├── module_detail.html
│   ├── lesson_view.html
│   ├── exercise_editor.html
│   ├── certificate_view.html
│   ├── user_dashboard.html
│   └── database_diagram.html
└── i18n (audela/i18n.py)
    └── SQL Training translations for all supported languages
```

## Database Schema

### SQLTrainingModule
- `code`: Unique module identifier (e.g., "sql_101")
- `title_i18n`: Multi-language titles
- `description_i18n`: Multi-language descriptions
- `level`: Difficulty (beginner, intermediate, advanced)
- `sample_database_schema`: DDL SQL for creating sample database
- `sample_data_sql`: INSERT SQL for populating sample data
- `pass_threshold`: Minimum % required to pass (default: 80)

### SQLTrainingLesson
- Theory and examples with HTML content
- Key concepts listing
- Multiple exercises per lesson
- Multi-language content support

### SQLTrainingExercise
- Exercise type: `sql_query` or `sql_dml`
- Expected SQL solutions
- Validation queries
- Point values
- Hints and instructions

### UserSQLTrainingEnrollment
- Tracks user progress in each module
- Stores overall score and pass status
- Maintains lesson progress JSON

### UserSQLTrainingSubmission
- Records each exercise submission
- Contains submitted SQL, result, feedback
- Tracks execution time and errors

### SQLTrainingCertificate
- Issued upon module completion
- Beautiful HTML certificate design
- Unique verification codes
- LinkedIn shareable

## URL Routes

### Public Routes
```
GET  /sql-training/                         # Module listing (public)
GET  /sql-training/verify-certificate/<code>  # Certificate verification
```

### Authenticated Routes
```
GET  /sql-training/module/<id>              # Module details & lessons
GET  /sql-training/lesson/<id>              # Lesson view with exercises
GET  /sql-training/exercise/<id>            # Exercise editor
GET  /sql-training/certificate/<id>         # View certificate
GET  /sql-training/dashboard                # User's training dashboard
GET  /sql-training/database-diagram/<id>    # Database schema diagram

# API Endpoints
POST /sql-training/api/submit-exercise      # Submit exercise solution
POST /sql-training/api/execute-query        # Execute query for practice
POST /sql-training/api/reset-database/<id>  # Reset sample database
GET  /sql-training/api/check-progress/<id>  # Get progress stats
GET  /sql-training/api/get-schema/<id>      # Get database schema
POST /sql-training/api/autocomplete-sql     # SQL autocomplete suggestions
POST /sql-training/api/complete-module/<id> # Complete module & generate cert
```

## SQL Execution Flow

### 1. Initialize Sample Database
```python
service = SQLTrainingService()
sample_db = service.get_or_create_sample_database(user_id, module_id)
# Creates SQLite database with module's DDL and sample data
```

### 2. Execute Query
```python
result = service.execute_query(
    module_id=1,
    user_id=current_user.id,
    query="SELECT * FROM customers"
)
# Returns: {result_data, columns, row_count, execution_time_ms}
```

### 3. Evaluate Exercise
```python
result = service.execute_and_evaluate_exercise(
    exercise=exercise_obj,
    enrollment=enrollment_obj,
    sql_code=user_sql,
    user_language="pt"
)
# Returns: {is_correct, points_earned, feedback_i18n, result_data, ...}
```

### 4. Generate Certificate
```python
is_passed, final_score = service.evaluate_module_completion(enrollment)
if is_passed:
    certificate = service.generate_certificate(enrollment)
    html = service.get_certificate_html(certificate, language="pt")
```

## Features in Detail

### Interactive SQL Editor
- Code syntax highlighting (Ace Editor or similar)
- SQL keywords quick reference
- Execute button with results display
- Previous attempts tracking
- Real-time result table

### Database Sandbox
- Isolated SQLite database per user+module
- Secure execution without DROP/ALTER/TRUNCATE
- Automatic cleanup after 30 days of inactivity
- Reset capability for users

### Progress Tracking
- Real-time progress percentage
- Per-lesson and per-exercise completion status
- Best score tracking for each exercise
- Overall module score calculation

### Certificate System
- Beautiful gradient design with user details
- Score and completion date display
- Unique certificate numbers for authenticity
- 12-character verification codes
- LinkedIn and Twitter share buttons  
- Print-to-PDF capability
- Expiry tracking (optional)

### Exercise Types

**SQL Query Exercises**
- Write and submit SQL queries
- Validation based on result comparison
- Feedback on incorrect results

**SQL DML Exercises**
- INSERT, UPDATE, DELETE operations
- Validation query to check results
- Points awarded on successful validation

### Multi-Language Support
- Full UI translation
- Content per language in i18n fields
- User language preference
- Fallback chain: requested → English → Portuguese → msgid

## Admin: Creating New Modules

### Via Seed Script
```bash
flask --app app seed-sql-training
```

### Manual Database Entry
```python
module = SQLTrainingModule(
    code="sql_advanced",
    title_i18n={"pt": "SQL Avançado", "en": "Advanced SQL"},
    description_i18n={...},
    level="advanced",
    sample_database_schema="CREATE TABLE...",
    sample_data_sql="INSERT INTO...",
    pass_threshold=80
)
db.session.add(module)
db.session.commit()
```

## User Flow

### 1. Browse Modules
- User visits `/sql-training/`
- Views all available modules by level
- Sees enrollment status and progress

### 2. Enroll & Learn
- Click "Start Learning" or "Continue"
- Auto-enrollment if not already enrolled
- Sample database created automatically

### 3. Complete Lessons
- Read theory and examples
- View database schema diagram
- Complete exercises sequentially

### 4. Practice Exercises
- Write SQL in editor
- Execute for testing
- Submit when confident
- See feedback immediately

### 5. Earn Certificate
- Upon completing all exercises with 80%+ score
- Certificate generated automatically
- Can download, print, or share on LinkedIn
- Verification code for authenticity check

### 6. Dashboard
- View all enrolled courses
- Check progress statistics
- Access all earned certificates
- Resume or start new courses

## Security Considerations

### SQL Injection Prevention
- Use parameterized queries for user input (PyODBC style)
- Isolate SQLite databases per user
- Read-only option during practice

### Dangerous Operations Prevention
- Restrict DROP, TRUNCATE, ALTER in sandbox
- Allow DML (INSERT, UPDATE, DELETE) only in exercises
- Query execution timeouts (30s default)
- Row limit enforcement

### Data Isolation
- Each user has their own sample database copy
- Databases expire after 30 days of inactivity
- Automatic cleanup prevents storage issues
- Tenant-scoped access control

## Performance Tips

### Database Queries
- Use indexes on frequently queried columns
- Pagination for result sets over 1000 rows
- Caching of module metadata
- Background task for certificate generation

### File Storage
- SQLite databases stored in `/tmp` by default
- Configure with `TENANT_FILE_ROOT` for production
- Consider S3 for distributed setups

### Frontend Optimization
- Lazy loading of exercise editor
- Code splitting for diagram component
- Minified CSS/JS
- CDN for D3.js library

## Deployment Checklist

- [ ] Run database migrations: `flask db upgrade`
- [ ] Seed sample modules: `flask seed-sql-training`
- [ ] Configure `TENANT_FILE_ROOT` for sandbox databases
- [ ] Set `FLASK_ENV=production`
- [ ] Configure SECRET_KEY and DATA_KEY
- [ ] Test email for certificate notifications (optional)
- [ ] Verify all language translations
- [ ] Test certificate generation and download
- [ ] Load test SQL sandbox with concurrent users
- [ ] Configure backup of user enrollment data

## Testing

### Local Development
```bash
# Create SQLite test database
export DATABASE_URL="sqlite:///./audela_test.db"

# Run migrations
flask db upgrade

# Seed sample data
flask seed-sql-training

# Start development server
flask run

# Visit http://localhost:5000/sql-training/
```

### Manual Testing Checklist
- [ ] Create user account
- [ ] Browse modules
- [ ] Enroll in course
- [ ] Complete lesson exercise
- [ ] Submit incorrect SQL (check feedback)
- [ ] Submit correct SQL (check points)
- [ ] View progress dashboard
- [ ] Complete 3+ exercises to hit 80% threshold
- [ ] Download and view certificate
- [ ] Share certificate link

## Future Enhancements

### Phase 2
- [ ] Leaderboards (top students by score)
- [ ] Peer code reviews / peer grading
- [ ] Timed challenges / tournaments
- [ ] YouTube-style video lessons
- [ ] Discussion forums per module

### Phase 3
- [ ] AI-powered SQL hints
- [ ] Plagiarism detection
- [ ] Integration with GitHub for SQL projects
- [ ] Corporate training dashboard
- [ ] Batch user enrollment via CSV

### Phase 4
- [ ] PostgreSQL/MySQL support (not just SQLite)
- [ ] Advanced window functions module
- [ ] Database design normalization course
- [ ] Real transaction management exercises
- [ ] Backup & recovery concepts

## Troubleshooting

### "Database not found" Error
```python
# Check sample database exists
sample_db = SQLTrainingSampleDatabase.query.filter_by(
    user_id=user_id, module_id=module_id
).first()
# Manually recreate:
service.reset_sample_database(user_id, module_id)
```

### SQL Execution Timeouts
- Increase timeout: `service.execute_query(..., timeout=60)`
- Optimize the SQL query
- Check for infinite loops in PRAGMA statements

### Certificate Not Generating
- Verify `pass_threshold` is met
- Check enrollment.passed = True
- Manually generate: `service.generate_certificate(enrollment)`

### Multi-Language Issues
- Check `SUPPORTED_LANGS` in i18n.py
- Verify translations in `TRANSLATIONS` dict
- Use `tr()` function for fallback
- Check browser Accept-Language header

## Support

For issues or feature requests, please create an issue in the AUDELA repository with tag `[sql-training]`.

---

**Status**: ✅ MVP Complete

**Last Updated**: May 13, 2026

**Module Version**: 1.0.0

