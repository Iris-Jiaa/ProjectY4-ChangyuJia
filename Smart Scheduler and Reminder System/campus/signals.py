from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from .models import MeetingRequest, Notification


@receiver(post_save, sender=MeetingRequest)
def create_meeting_request_notification(sender, instance, created, **kwargs):
    if created:
        recipient = instance.lecturer.staff
        message = f"New meeting request from {instance.student.student_name.get_full_name()} for {instance.title}."
        content_type = ContentType.objects.get_for_model(instance)
        Notification.objects.create(
            recipient=recipient,
            message=message,
            content_type=content_type,
            object_id=instance.id,
        )
