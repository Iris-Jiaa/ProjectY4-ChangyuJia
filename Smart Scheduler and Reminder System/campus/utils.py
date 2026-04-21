from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import uuid

from django.db.models import Q
from django.utils import timezone

from campus.models import Holiday, Lecture, RegisteredUnit, StudentPersonalEvent, FacultyPersonalEvent


def is_holiday_date(date):
    """Return True if the given date falls within any admin-configured Holiday period."""
    return Holiday.objects.filter(start_date__lte=date, end_date__gte=date).exists()


class EventItem:
    """ A standardized representation for various types of events to facilitate conflict detection. """
    def __init__(self, obj_id, title, start_datetime, end_datetime, location=None, event_type='unknown'):
        self.obj_id = obj_id
        self.title = title
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.location = location  # String representation of location (e.g., hall_no)
        self.event_type = event_type # 'lecture' or 'personal_event'

    def __str__(self):
        return (f"{self.title} (ID: {self.obj_id}) from {self.start_datetime} to {self.end_datetime}"
                f"{' at ' + self.location if self.location else ''} [{self.event_type}]")

def check_student_conflicts(student):
    all_events = []

    # 1. Fetch and normalize Lectures
    # Get all registered units for the student
    registered_units = RegisteredUnit.objects.filter(student=student)
    # Find all lectures associated with these registered units
    lectures_qs = Lecture.objects.filter(
        unit_name__in=registered_units.values('unit')
    ).select_related('lecturer__staff', 'unit_name__course', 'lecture_hall')

    for lecture in lectures_qs:
        # Combine date and time fields into timezone-aware datetime objects
        start_datetime = timezone.make_aware(datetime.combine(lecture.lecture_date, lecture.start_time))
        end_datetime = timezone.make_aware(datetime.combine(lecture.lecture_date, lecture.end_time))
        location = lecture.lecture_hall.hall_no if lecture.lecture_hall else None
        all_events.append(EventItem(
            obj_id=lecture.id,
            title=f"{lecture.unit_name.course.name} ({lecture.lecturer.staff.first_name} {lecture.lecturer.staff.last_name})",
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            location=location,
            event_type='lecture'
        ))

    # 2. Fetch and normalize StudentPersonalEvents
    personal_events_qs = StudentPersonalEvent.objects.filter(student=student)
    for personal_event in personal_events_qs:
        all_events.append(EventItem(
            obj_id=personal_event.id,
            title=personal_event.title,
            start_datetime=personal_event.start_date,
            end_datetime=personal_event.end_date,
            location=None, # Personal events don't have a fixed lecture hall
            event_type='personal_event'
        ))

    # 3. Sort events by start time
    all_events.sort(key=lambda x: x.start_datetime)

    conflicts = []

    # 4. Detect conflicts
    # Compare each event with every other event
    for i in range(len(all_events)):
        for j in range(i + 1, len(all_events)):
            event1 = all_events[i]
            event2 = all_events[j]

            # Check for time overlap
            if event1.start_datetime < event2.end_datetime and event2.start_datetime < event1.end_datetime:
                # Time conflict detected
                conflict = {
                    'type': 'time_overlap',
                    'description': f"Time overlap detected between '{event1.title}' and '{event2.title}'.",
                    'events': [event1, event2]
                }
                conflicts.append(conflict)

                # Check for location conflict if both events have a defined location and are different
                if event1.location and event2.location and event1.location != event2.location:
                    location_conflict = {
                        'type': 'location_conflict',
                        'description': f"Location conflict: '{event1.title}' at '{event1.location}' and '{event2.title}' at '{event2.location}' at the same time.",
                        'events': [event1, event2]
                    }
                    conflicts.append(location_conflict)
    
    return conflicts

def create_recurring_instances(instance):
    """
    Creates multiple instances of a Lecture or PersonalEvent based on its recurrence pattern.
    The 'instance' is the first (parent) event.
    """
    # If no recurrence, return the single instance
    if not instance.recurrence_pattern or instance.recurrence_pattern == 'none':
        return [instance]

    instances = [instance]
    parent_id = instance.id
    instance.parent_event_id = parent_id
    instance.save() # Save again after setting parent_event_id

    pattern = instance.recurrence_pattern
    end_type = instance.recurrence_end_type
    
    current_start = getattr(instance, 'start_date', None)
    current_end = getattr(instance, 'end_date', None)
    current_lecture_date = getattr(instance, 'lecture_date', None)
    
    # Delta calculation
    if pattern == 'daily':
        delta = timedelta(days=1)
    elif pattern == 'weekly':
        delta = timedelta(weeks=1)
    elif pattern == 'monthly':
        delta = relativedelta(months=1)
    else:
        return [instance]

    # End condition
    count = instance.recurrence_count if end_type == 'count' else 999
    end_date = instance.recurrence_end_date if end_type == 'date' else None

    occurrences = 1
    while True:
        if end_type == 'count' and occurrences >= count:
            break
        
        # Calculate next dates
        next_date_obj = None
        next_start_datetime = None
        next_end_datetime = None

        if current_start: # For personal events (start_date, end_date)
            current_start += delta
            current_end += delta
            next_date_obj = current_start.date()
            next_start_datetime = current_start
            next_end_datetime = current_end
        elif current_lecture_date: # For lectures (lecture_date)
            current_lecture_date += delta
            next_date_obj = current_lecture_date
            # For lectures, we need to combine with original start/end times
            original_start_time = instance.start_time
            original_end_time = instance.end_time
            next_start_datetime = timezone.make_aware(datetime.combine(current_lecture_date, original_start_time))
            next_end_datetime = timezone.make_aware(datetime.combine(current_lecture_date, original_end_time))
        
        if end_date and next_date_obj and next_date_obj > end_date:
            break
        
        # Create new instance
        model_class = instance.__class__
        new_instance = model_class.objects.get(id=instance.id)
        new_instance.pk = None # This ensures a new object is created
        new_instance.id = str(uuid.uuid4())
        new_instance.parent_event_id = parent_id
        
        if next_start_datetime and next_end_datetime:
            if hasattr(new_instance, 'start_date'): # Personal Event type
                new_instance.start_date = next_start_datetime
                new_instance.end_date = next_end_datetime
            elif hasattr(new_instance, 'lecture_date'): # Lecture type
                new_instance.lecture_date = next_date_obj
                new_instance.start_time = next_start_datetime.time()
                new_instance.end_time = next_end_datetime.time()
        
        try:
            new_instance.save()
            instances.append(new_instance)
        except Exception as e:
            # Conflict or other error, skip this instance or handle as needed
            print(f"Error creating recurring instance: {e}") # Log the error
            break
            
        occurrences += 1
    
    return instances
