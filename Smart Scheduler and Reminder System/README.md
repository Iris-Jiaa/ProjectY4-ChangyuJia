# ProjectY4-ChangyuJia
# Smart Scheduler and Reminder System

## Overview

This system is a professional web-based application designed to address the common scheduling and communication challenges faced by educational institutions. It supports three user roles — **Admin**, **Faculty (Lecturer)**, and **Student** — and provides the following core features:

- **Lecture management** with venue conflict detection enforced at the model layer
- **Meeting requests** between students and lecturers, with a full approval workflow and conflict checking
- **Personal event management** for both students and faculty, with recurrence (daily / weekly / monthly) and priority levels
- **Smart reminders** delivered via in-app notifications and/or email at configurable lead times (60 min, 30 min, 15 min, instant)
- **Attendance tracking** with automatic warnings when a student's attendance rate falls below 75%
- **Holiday / exam-week management** that auto-exempts events falling on admin-defined periods

## Prerequisites

- Python 3.8+

## Running the Project Locally

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
```

```bash
# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Apply database migrations

```bash
python manage.py migrate
```

### 4. Create a superuser (Admin account)

```bash
python manage.py createsuperuser
```

### 5. Start Redis (message broker)

Celery requires a running Redis instance. Start it as a background process:

```powershell
# Windows — run once per session (or after reboot)
Start-Process -FilePath "redis-server" -WindowStyle Hidden
```

Verify Redis is up:

```bash
redis-cli -h 127.0.0.1 ping
# Expected output: PONG
```

> **Note:** Redis runs as a background process and stops when the machine reboots.  
> To make it persist across reboots, install Redis as a Windows service (tick  
> *"Add to PATH as service"* during installation).

### 6. Start the Celery worker

Open a new terminal:

```bash
celery -A src worker -l info -P solo
```

Expected output:
```
[celery@... INFO] Connected to redis://127.0.0.1:6379/0
[celery@... INFO] celery@... ready.
```

### 7. Start Celery Beat (periodic task scheduler)

Open another new terminal:

```bash
celery -A src beat -l info
```

Expected output:
```
[INFO] beat: Starting...
[INFO] Scheduler: Sending due task personal-event-reminders
```

### 8. Start the development server

```bash
python manage.py runserver
```

The application will be available at **http://127.0.0.1:8000**.

> **Startup order:** Redis → Celery Worker → Celery Beat → Django

## Project Structure

```
├── accounts/        # Custom User model, Student, Faculty; auth views; reminder settings
│   └── tests.py         # Unit tests: user model, roles, student/faculty profiles (16 tests)
├── campus/          # Core app — lectures, meetings, personal events, notifications
│   ├── tasks.py              # Notification and reminder helper functions
│   ├── models.py             # All domain models with conflict validation
│   ├── tests.py              # Unit & integration tests: conflict detection, RBAC, views (42 tests)
│   └── tests_performance.py  # Performance tests: response time, N+1, throughput (14 tests)
├── new_features/    # Admin unit-assignment extension
├── src/             # Django project settings and URLs
└── manage.py
```

---

## Database

The project uses **SQLite** (`db.sqlite3` in the project root). All table structures are defined in `models.py` and managed through Django's migration system — no manual SQL is required for normal operation.

### Viewing the database — Django Shell (ORM)

```bash
python manage.py shell
```

```python
from accounts.models import User
from campus.models import Lecture, MeetingRequest, Notification

User.objects.count()                                    # total users
Lecture.objects.filter(status='scheduled').count()      # upcoming lectures
MeetingRequest.objects.filter(status='pending').count() # pending meeting requests
Notification.objects.filter(is_read=False).count()      # unread notifications
```

### Viewing the database — `dbshell` (direct SQL)

```bash
python manage.py dbshell
```

```sql
-- List all tables
.tables

-- Show table schema
.schema campus_lecture

-- Query data
SELECT * FROM campus_lecture LIMIT 10;

-- Exit
.quit
```

### Modifying the database structure

Any change to `models.py` (adding a field, a new model, etc.) must be followed by:

```bash
# 1. Generate a migration file from the model changes
python manage.py makemigrations

# 2. Apply the migration to the database
python manage.py migrate
```

To check the status of all migrations:

```bash
python manage.py showmigrations
```

`[X]` = applied, `[ ]` = pending.

To roll back to a specific migration:

```bash
python manage.py migrate campus 0017
```

### Migration history

| App | Migrations | Notable changes |
|-----|-----------|----------------|
| `accounts` | 0001 – 0006 | Custom User model, Student/Faculty profiles, reminder preferences |
| `campus` | 0001 – 0018 | Lectures, meetings, personal events, notifications, holidays, comments, per-event reminder times |

---

## Running Tests

### Unit Tests — all modules

```bash
python manage.py test accounts campus --verbosity=2
```

Expected result:
```
Ran 58 tests in ~15s
OK
```

### Run a specific test class

```bash
python manage.py test campus.tests.LectureVenueConflictTests --verbosity=2
python manage.py test campus.tests.RBACPermissionTests --verbosity=2
```

### Performance Tests

Covers four dimensions: response time, N+1 query detection, conflict detection accuracy & speed, notification bulk throughput.

```bash
python manage.py test campus.tests_performance --verbosity=2
```

Expected result:
```
Ran 14 tests in ~6s
OK (skipped=2)
```

> The 2 skipped tests (`ConcurrentUserTests`) require PostgreSQL to run.
> SQLite does not support multi-threaded concurrent connections; they pass in the production PostgreSQL environment.

### Performance Benchmarks

| Test | Result | Threshold |
|------|--------|-----------|
| Student homepage response time | ~22ms (median) | < 500ms |
| Personal report page response time | ~8ms | < 500ms |
| Calendar events API response time | ~2ms | < 200ms |
| Holidays API response time | ~1ms | < 200ms |
| Admin dashboard response time | ~4ms | < 500ms |
| SQL query count (10 → 20 courses, delta) | **0** | ≤ 5 (no N+1) |
| Student event conflict detection accuracy | 10/10 = **100%** | 100% |
| Lecture venue conflict detection accuracy | 10/10 = **100%** | 100% |
| Conflict detection speed (50 existing events) | ~0.25ms (median) | < 50ms |
| Bulk notification creation (50 records) | ~30ms total | < 2000ms |
| Bulk mark-read SQL queries | **1** UPDATE | 1 |

### Test Coverage Summary

| Test Class | Coverage |
|-----------|---------|
| `UserModelTests` | User creation, default reminder settings, field updates |
| `StudentProfileTests` | Student profile linking, `is_student_user` property |
| `FacultyProfileTests` | Faculty profile, `is_faculty` / `is_admin` role properties |
| `AdminRoleTests` | Superuser & Admin position admin detection |
| `CourseModelTests` | Course creation, duplicate code rejection |
| `HolidayValidationTests` | Holiday date validation |
| `LectureVenueConflictTests` | Venue concurrent booking conflict detection (core feature) |
| `FacultyPersonalEventConflictTests` | Faculty event time conflict & adjacent slot allowed |
| `StudentPersonalEventConflictTests` | Student event conflict & different-user no-conflict |
| `MeetingRequestConflictTests` | Meeting location conflict detection |
| `MeetingRequestWorkflowTests` | All 7 meeting request status transitions |
| `EventStatusJudgementTests` | Auto-judge lecture & personal event status |
| `RBACPermissionTests` | Role permission isolation (anonymous / student / lecturer / admin) |
| `PersonalReportTests` | Report view 200 response & correct context stats |
| `BidirectionalCalendarAPITests` | Calendar API returns JSON & data isolation per user |
| `NotificationModelTests` | Notification creation, mark-read, bulk mark-read |
