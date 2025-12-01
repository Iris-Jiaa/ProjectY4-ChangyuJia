from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction

class Command(BaseCommand):
    help = 'Deletes new message notifications sent by Teacher Jia.'

    def handle(self, *args, **options):
        User = apps.get_model('accounts', 'User')
        Notification = apps.get_model('campus', 'Notification')

        try:
            # Attempt to find "Teacher Jia"
            # Assuming 'Jia' is the first name and they are a faculty member.
            # This might need refinement based on actual data.
            teacher_jia = User.objects.get(first_name='Jia', faculty__isnull=False)
            self.stdout.write(self.style.SUCCESS(f"Found Teacher Jia: {teacher_jia.get_full_name()} (ID: {teacher_jia.id})"))
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR("Error: Teacher Jia not found. Please ensure a user with first name 'Jia' exists and is associated with a faculty record."))
            return
        except User.MultipleObjectsReturned:
            self.stderr.write(self.style.ERROR("Error: Multiple users found with first name 'Jia' who are faculty members. Please refine the search criteria."))
            return

        # Identify notifications sent by Teacher Jia that are "new message" related
        # This filter is an assumption and might need adjustment based on your notification logic.
        # Common patterns could be specific notification_type or keywords in the message.
        # For this example, we'll look for messages containing "new message" or similar phrases.
        # You may need to adjust this filter based on how "new message" notifications are generated.
        notifications_to_delete = Notification.objects.filter(
            sender=teacher_jia,
            notification_type__icontains='message' # Example: assuming 'message' is in notification_type
        ) | Notification.objects.filter(
            sender=teacher_jia,
            message__icontains='new message' # Example: assuming message contains "new message"
        )

        if not notifications_to_delete.exists():
            self.stdout.write(self.style.SUCCESS("No new message notifications found for Teacher Jia."))
            return

        self.stdout.write(self.style.WARNING(f"Found {notifications_to_delete.count()} notifications to delete."))
        
        confirm = input("Are you sure you want to delete these notifications? Type 'yes' to confirm: ")
        
        if confirm.lower() == 'yes':
            with transaction.atomic():
                deleted_count, _ = notifications_to_delete.delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} new message notifications from Teacher Jia."))
        else:
            self.stdout.write(self.style.NOTICE("Deletion cancelled."))

