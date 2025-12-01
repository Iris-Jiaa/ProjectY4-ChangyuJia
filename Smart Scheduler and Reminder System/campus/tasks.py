from celery import shared_task
from datetime import timedelta, datetime
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from .models import Lecture, Notification, MeetingRequest
from accounts.models import User

@shared_task
def send_email_notification(user_id, subject, message):
    """Sends an email notification to a user."""
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
        # Handle case where user is not found
        pass
    except Exception as e:
        # Handle other potential exceptions (e.g., SMTP errors)
        print(f"Failed to send email to user {user_id}: {e}")


def _send_notification(user, content_object, message):
    """Helper function to create an in-app notification and trigger an email if needed."""
    content_type = ContentType.objects.get_for_model(content_object)
    
    # Send In-App Notification
    if user.notification_method in ['in_app', 'both']:
        if not Notification.objects.filter(recipient=user, content_type=content_type, object_id=content_object.id).exists():
            Notification.objects.create(
                recipient=user,
                message=message,
                content_type=content_type,
                object_id=content_object.id,
            )

    # Send Email Notification
    if user.notification_method in ['email', 'both']:
        subject = f"Smart-Scheduler Reminder: {message[:50]}..."
        send_email_notification.delay(user.id, subject, message)


@shared_task
def send_upcoming_lecture_notifications():
    now = timezone.now()
    
    lectures = Lecture.objects.filter(
        lecture_date=now.date(), 
        start_time__gte=now.time()
    ).select_related('lecturer__staff', 'unit_name')

    for lecture in lectures:
        lecture_start_datetime = timezone.make_aware(
            datetime.combine(lecture.lecture_date, lecture.start_time)
        )
        time_until_lecture = lecture_start_datetime - now

        users = []
        if lecture.lecturer and hasattr(lecture.lecturer, 'staff'):
            users.append(lecture.lecturer.staff)
        
        students = User.objects.filter(student__registeredunit__unit=lecture.unit_name)
        users.extend(students)

        for user in set(users):
            # User preferences can contain multiple values, e.g., "60min,15min"
            user_preferences = user.reminder_preference.split(',')

            for pref in user_preferences:
                message = ""
                should_send = False

                if pref == '60min' and timedelta(minutes=59, seconds=30) <= time_until_lecture < timedelta(minutes=60, seconds=30):
                    message = f"Reminder: Your course '{lecture.unit_name.course_name}' is starting in 60 minutes."
                    should_send = True
                elif pref == '30min' and timedelta(minutes=29, seconds=30) <= time_until_lecture < timedelta(minutes=30, seconds=30):
                    message = f"Reminder: Your course '{lecture.unit_name.course_name}' is starting in 30 minutes."
                    should_send = True
                elif pref == '15min' and timedelta(minutes=14, seconds=30) <= time_until_lecture < timedelta(minutes=15, seconds=30):
                    message = f"Reminder: Your course '{lecture.unit_name.course_name}' is starting in 15 minutes."
                    should_send = True
                elif pref == 'instant' and timedelta(seconds=0) <= time_until_lecture < timedelta(seconds=30):
                    message = f"Reminder: Your course '{lecture.unit_name.course_name}' is starting now."
                    should_send = True

                if should_send:
                    _send_notification(user, lecture, message)


@shared_task
def send_upcoming_meeting_notifications():
    now = timezone.now()
    
    meetings = MeetingRequest.objects.filter(
        status='approved',
        start_time__gte=now,
    ).select_related('student__student_name', 'lecturer__staff')

    for meeting in meetings:
        time_until_meeting = meeting.start_time - now

        participants = []
        if hasattr(meeting, 'student') and hasattr(meeting.student, 'student_name'):
             participants.append(meeting.student.student_name)
        if hasattr(meeting, 'lecturer') and hasattr(meeting.lecturer, 'staff'):
            participants.append(meeting.lecturer.staff)

        for user in participants:
            other_participant_name = ""
            if hasattr(user, 'is_student') and user.is_student:
                other_participant_name = meeting.lecturer.staff.get_full_name()
            else:
                if hasattr(meeting.student, 'student_name'):
                    other_participant_name = meeting.student.student_name.get_full_name()

            user_preferences = user.reminder_preference.split(',')

            for pref in user_preferences:
                should_send = False
                time_description = ""

                if pref == '60min' and timedelta(minutes=59, seconds=30) <= time_until_meeting < timedelta(minutes=60, seconds=30):
                    should_send = True
                    time_description = "in 60 minutes"
                elif pref == '30min' and timedelta(minutes=29, seconds=30) <= time_until_meeting < timedelta(minutes=30, seconds=30):
                    should_send = True
                    time_description = "in 30 minutes"
                elif pref == '15min' and timedelta(minutes=14, seconds=30) <= time_until_meeting < timedelta(minutes=15, seconds=30):
                    should_send = True
                    time_description = "in 15 minutes"
                elif pref == 'instant' and timedelta(seconds=0) <= time_until_meeting < timedelta(seconds=30):
                    should_send = True
                    time_description = "now"

                if should_send:
                    message = f"Reminder: You have a meeting with {other_participant_name} titled '{meeting.title}' starting {time_description}."
                    _send_notification(user, meeting, message)
