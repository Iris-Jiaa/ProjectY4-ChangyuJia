"""
Celery periodic tasks for the Smart Scheduler & Reminder System.

Beat schedule (every 60 s) triggers four tasks:
  1. send_personal_event_reminders  – personal events for students & faculty
  2. send_upcoming_lecture_notifications  – scheduled lectures
  3. send_upcoming_meeting_notifications  – approved meeting requests
  4. auto_judge_event_statuses  – mark past events completed / missed (every 5 min)
"""

from celery import shared_task
from datetime import timedelta, datetime

from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import (
    Holiday, Lecture, Notification,
    MeetingRequest, StudentPersonalEvent, FacultyPersonalEvent,
    RegisteredUnit,
)

# ── Shared reminder window definitions ───────────────────────────────────────
# Each entry: pref_key → (lower_bound, upper_bound, human description)
# The task runs every 60 s; windows are ±30 s around the nominal offset so
# exactly one task tick falls inside each window.

REMINDER_WINDOWS = {
    '60min':   (timedelta(minutes=59, seconds=30), timedelta(minutes=60, seconds=30), 'in 60 minutes'),
    '30min':   (timedelta(minutes=29, seconds=30), timedelta(minutes=30, seconds=30), 'in 30 minutes'),
    '15min':   (timedelta(minutes=14, seconds=30), timedelta(minutes=15, seconds=30), 'in 15 minutes'),
    'instant': (timedelta(seconds=0),              timedelta(seconds=30),             'now'),
}

# Maximum look-ahead: slightly beyond the 60-min window so the DB query is
# tight and doesn't pull events hours away.
MAX_LOOKAHEAD = timedelta(hours=1, seconds=30)


def _match_window(time_until, prefs):
    """
    Given a timedelta and a list of preference keys, return the first
    (pref_key, description) whose window contains *time_until*, or (None, None).
    """
    for pref in prefs:
        window = REMINDER_WINDOWS.get(pref)
        if window:
            low, high, desc = window
            if low <= time_until < high:
                return pref, desc
    return None, None


# ── In-app / email delivery helper ───────────────────────────────────────────

def _send_notification(user, content_object, message):
    """
    Create an in-app Notification and/or trigger an email.

    Deduplication key: recipient + event (content_type + object_id) + message.
    This allows multiple distinct reminders (60min, 30min, 15min, instant)
    for the same event while still preventing the same reminder from being
    delivered twice if the task happens to run twice in the same window.
    """
    content_type = ContentType.objects.get_for_model(content_object)

    if user.notification_method in ('in_app', 'both'):
        already_sent = Notification.objects.filter(
            recipient=user,
            content_type=content_type,
            object_id=content_object.id,
            message=message,
        ).exists()
        if not already_sent:
            Notification.objects.create(
                recipient=user,
                message=message,
                content_type=content_type,
                object_id=content_object.id,
            )

    if user.notification_method in ('email', 'both'):
        subject = f"Smart-Scheduler Reminder: {message[:70]}"
        send_email_notification.delay(str(user.id), subject, message)


# ── Email task ────────────────────────────────────────────────────────────────

@shared_task
def send_email_notification(user_id, subject, message):
    """Send an email to a single user (called via .delay())."""
    from accounts.models import User
    try:
        user = User.objects.get(id=user_id)
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )
    except User.DoesNotExist:
        pass
    except Exception as exc:
        print(f"[send_email_notification] Failed for user {user_id}: {exc}")


# ── Personal-event reminders ─────────────────────────────────────────────────

@shared_task
def send_personal_event_reminders():
    now = timezone.now()
    horizon = now + MAX_LOOKAHEAD

    student_events = (
        StudentPersonalEvent.objects
        .filter(start_date__gte=now, start_date__lte=horizon, status='pending')
        .select_related('student__student_name')
    )
    faculty_events = (
        FacultyPersonalEvent.objects
        .filter(start_date__gte=now, start_date__lte=horizon, status='pending')
        .select_related('faculty__staff')
    )

    for event in list(student_events) + list(faculty_events):
        time_until = event.start_date - now

        # Resolve the owning user
        if hasattr(event, 'student'):
            user = event.student.student_name
        elif hasattr(event, 'faculty'):
            user = event.faculty.staff
        else:
            continue

        prefs = [p.strip() for p in user.reminder_preference.split(',') if p.strip()]
        sent  = [r.strip() for r in (event.sent_reminders or '').split(',') if r.strip()]

        pref_key, desc = _match_window(time_until, prefs)
        if not pref_key or pref_key in sent:
            continue

        message = f"Reminder: Your event '{event.title}' is starting {desc}."
        _send_notification(user, event, message)

        # Persist sent_reminders without triggering full_clean / conflict checks
        sent.append(pref_key)
        type(event).objects.filter(pk=event.pk).update(sent_reminders=','.join(sent))


# ── Lecture reminders ─────────────────────────────────────────────────────────

@shared_task
def send_upcoming_lecture_notifications():
    from accounts.models import User

    now = timezone.now()

    # Only look at lectures that start today and haven't passed
    lectures = (
        Lecture.objects
        .filter(lecture_date=now.date(), status='scheduled')
        .select_related('lecturer__staff', 'unit_name__course')
    )

    for lecture in lectures:
        lecture_start = timezone.make_aware(
            datetime.combine(lecture.lecture_date, lecture.start_time)
        )
        time_until = lecture_start - now

        # Skip if outside the maximum look-ahead window or already started
        if not (timedelta(0) <= time_until <= MAX_LOOKAHEAD):
            continue

        # Build participant list: the lecturer + all registered students
        users = set()
        if lecture.lecturer and lecture.lecturer.staff:
            users.add(lecture.lecturer.staff)

        registered_students = User.objects.filter(
            student__registeredunit__unit=lecture.unit_name
        )
        users.update(registered_students)

        course_name = lecture.unit_name.course.name

        for user in users:
            prefs = [p.strip() for p in user.reminder_preference.split(',') if p.strip()]
            pref_key, desc = _match_window(time_until, prefs)
            if not pref_key:
                continue

            message = f"Reminder: Lecture '{course_name}' is starting {desc}."
            _send_notification(user, lecture, message)


# ── Meeting-request reminders ─────────────────────────────────────────────────

@shared_task
def send_upcoming_meeting_notifications():
    now = timezone.now()
    horizon = now + MAX_LOOKAHEAD

    meetings = (
        MeetingRequest.objects
        .filter(status='approved', start_time__gte=now, start_time__lte=horizon)
        .select_related('student__student_name', 'lecturer__staff')
    )

    for meeting in meetings:
        time_until = meeting.start_time - now

        participants = []
        if meeting.student and meeting.student.student_name:
            participants.append(meeting.student.student_name)
        if meeting.lecturer and meeting.lecturer.staff:
            participants.append(meeting.lecturer.staff)

        for user in participants:
            prefs = [p.strip() for p in user.reminder_preference.split(',') if p.strip()]
            pref_key, desc = _match_window(time_until, prefs)
            if not pref_key:
                continue

            # Address the notification to "the other party"
            if user.is_student:
                other = meeting.lecturer.staff.get_full_name()
            else:
                other = meeting.student.student_name.get_full_name()

            message = f"Reminder: Meeting '{meeting.title}' with {other} is starting {desc}."
            _send_notification(user, meeting, message)


# ── Auto-judge event statuses (runs every 5 min) ──────────────────────────────

@shared_task
def auto_judge_event_statuses():
    now = timezone.now()

    def _is_holiday(date):
        return Holiday.objects.filter(start_date__lte=date, end_date__gte=date).exists()

    # 1. Lectures
    for lecture in Lecture.objects.filter(status='scheduled'):
        if _is_holiday(lecture.lecture_date):
            Lecture.objects.filter(pk=lecture.pk).update(status='exempt')
            continue
        end_dt = timezone.make_aware(datetime.combine(lecture.lecture_date, lecture.end_time))
        if end_dt < now:
            new_status = 'completed' if (lecture.total_students > 0 or lecture.is_attending) else 'missed'
            Lecture.objects.filter(pk=lecture.pk).update(status=new_status)

    # 2. Student personal events
    for event in StudentPersonalEvent.objects.filter(status='pending'):
        if _is_holiday(event.start_date.date()):
            StudentPersonalEvent.objects.filter(pk=event.pk).update(status='exempt')
            continue
        if event.end_date < now:
            new_status = 'completed' if event.is_signed_in else 'missed'
            StudentPersonalEvent.objects.filter(pk=event.pk).update(status=new_status)

    # 3. Faculty personal events
    for event in FacultyPersonalEvent.objects.filter(status='pending'):
        if _is_holiday(event.start_date.date()):
            FacultyPersonalEvent.objects.filter(pk=event.pk).update(status='exempt')
            continue
        if event.end_date < now:
            new_status = 'completed' if event.is_signed_in else 'missed'
            FacultyPersonalEvent.objects.filter(pk=event.pk).update(status=new_status)

    # 4. Meeting requests
    for meeting in MeetingRequest.objects.filter(
        status__in=('approved', 'pending'), end_time__lt=now
    ):
        new_status = 'completed' if meeting.is_signed_in else 'missed'
        MeetingRequest.objects.filter(pk=meeting.pk).update(status=new_status)


# ── Attendance warning (runs once daily) ─────────────────────────────────────

ATTENDANCE_THRESHOLD = 0.75
ATTENDANCE_MIN_LECTURES = 3   # don't warn until at least 3 lectures have been held


@shared_task
def check_attendance_warnings():
    """
    For every registered unit, calculate the student's attendance rate.
    If it falls below ATTENDANCE_THRESHOLD and hasn't been warned in the
    last 7 days, send an in-app (and optionally email) notification.
    """
    week_ago = timezone.now() - timedelta(days=7)

    registrations = (
        RegisteredUnit.objects
        .filter(is_registered=True)
        .select_related('student__student_name', 'unit__course')
    )

    for reg in registrations:
        student = reg.student
        booked_unit = reg.unit
        user = student.student_name

        finalized = Lecture.objects.filter(
            student=student,
            unit_name=booked_unit,
            status__in=('completed', 'missed'),
        )
        total = finalized.count()
        if total < ATTENDANCE_MIN_LECTURES:
            continue

        attended = finalized.filter(is_attending=True).count()
        rate = attended / total

        if rate >= ATTENDANCE_THRESHOLD:
            continue

        course_name = booked_unit.course.name
        message = (
            f"Attendance Warning: Your attendance for '{course_name}' is "
            f"{int(rate * 100)}% — below the required 75%. "
            f"Please attend more classes to avoid academic penalties."
        )

        # Send at most once per 7 days per unit per student
        already_warned = Notification.objects.filter(
            recipient=user,
            message__startswith=f"Attendance Warning: Your attendance for '{course_name}'",
            date_created__gte=week_ago,
        ).exists()

        if not already_warned:
            _send_notification(user, booked_unit, message)
