from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from .models import MeetingRequest, Notification
from .tasks import send_email_notification


@receiver(post_save, sender=MeetingRequest)
def create_meeting_request_notification(sender, instance, created, **kwargs):
    if created:
        recipient = instance.lecturer.staff
        message = f"New meeting request from {instance.student.student_name.get_full_name()} for {instance.title}."
        
        # Check user's notification preference and send accordingly
        
        # 1. In-App Notification
        if recipient.notification_method in ['in_app', 'both']:
            content_type = ContentType.objects.get_for_model(instance)
            Notification.objects.create(
                recipient=recipient,
                message=message,
                content_type=content_type,
                object_id=instance.id,
            )

        # 2. Email Notification
        if recipient.notification_method in ['email', 'both']:
            subject = f"New Meeting Request: {instance.title}"
            send_email_notification.delay(recipient.id, subject, message)