from datetime import datetime, timedelta

from django.db.models import Q

from campus.models import Lecture, RegisteredUnit, StudentPersonalEvent

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
        # Combine date and time fields into datetime objects
        start_datetime = datetime.combine(lecture.lecture_date, lecture.start_time)
        end_datetime = datetime.combine(lecture.lecture_date, lecture.end_time)
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
