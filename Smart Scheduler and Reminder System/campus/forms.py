from .models import BookedUnit, Course, Feedback, Lecture, RegisteredUnit, StudentPersonalEvent, MeetingRequest, LectureHall, FacultyPersonalEvent
from accounts.models import Faculty
from django import forms
from datetime import datetime, timedelta # Import datetime and timedelta for potential usage in forms
from .utils import check_student_conflicts, EventItem

class StudentUnitsRegistrationForm(forms.ModelForm):
    unit = forms.ChoiceField(widget=forms.SelectMultiple(attrs={
            'type': 'select', 'class': 'mb-0',
        }),
        help_text='You can select multiple units.',
        label='Units',    
    )

    class Meta:
        model = RegisteredUnit
        fields = ['unit']

class StudentsAttendanceConfirmationForm(forms.ModelForm):
    lecture_date = forms.DateField(widget=forms.DateInput(attrs={
            'type': 'date', 'class': 'mb-0',
        }),
        help_text='Schedule a date for this lecture',
        disabled=True,
    )
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={
            'type': 'time', 'class': 'mb-0',
        }),
        help_text='At what time will this lecture begin?',
        label='Schedule start time',
        disabled=True,
    )
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={
            'type': 'time', 'class': 'mb-0',
        }),
        help_text='At what time will this lecture end?',
        label='Schedule end time',
        disabled=True,
    )
    is_attending = forms.BooleanField(widget=forms.CheckboxInput(attrs={
            'type': 'checkbox', 'class': 'my-2',
        }),
        help_text='I will be attending the class',
        required=True,
    )

    class Meta:
        model = Lecture
        fields = ['lecture_date', 'start_time', 'end_time', 'is_attending']

class LecturerUnitsBookingForm(forms.Form): # Changed to forms.Form
    SELECT_STUDENT_COURSE = (
        (None, '-- Select your course --'),
        ('Agribusiness', 'Agricultural Business'),
        ('Applied mathematics', 'Applied Mathematics'),
        ('Applied statictics', 'Applied Statictics'),
        ('Computer Science', 'Computer Science'),
        ('Education', 'Education'),
    )
    SELECT_YEAR_OF_STUDY = (
        (None, '-- Select year of study --'),
        ('1st year', 'First years (Freshers)'),
        ('2nd year', 'Second years (Sophomores)'),
        ('3rd year', 'Third years (Juniors)'),
        ('4th year', 'Fourth years (Seniors)'),
    )
    SELECT_SEMESTER = (
        (None, '-- Select semester --'),
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
    )

    lecturer = forms.ModelChoiceField(
        queryset=Faculty.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Lecturer'
    )
    courses = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter course names separated by commas'}),
        label='Courses to assign',
        help_text='Enter course names to assign to the lecturer (e.g., "Mathematics, Physics").'
    )
    students_course = forms.ChoiceField(widget=forms.Select(attrs={
            'type': 'select', 'class': 'mb-0',
        }),
        choices=SELECT_STUDENT_COURSE,
        label='Students course group',
        help_text='Which students will be studying this unit?'
    )
    year_of_study = forms.ChoiceField(widget=forms.Select(attrs={
            'type': 'select', 'class': 'mb-0',
        }),
        choices=SELECT_YEAR_OF_STUDY,
        label='Year of study',
        help_text='This unit will be studied by students of which year?',
    )
    semester = forms.ChoiceField(widget=forms.Select(attrs={
            'type': 'select', 'class': 'mb-0',
        }),
        choices=SELECT_SEMESTER,
        help_text='This unit will be studied by students of which semester?',
    )

    def __init__(self, *args, **kwargs):
        super(LecturerUnitsBookingForm, self).__init__(*args, **kwargs)
        # No need to filter lecturer queryset here as it's a direct field now
        # self.fields['lecturer'].queryset = Faculty.objects.filter()


class FeedbackForm(forms.ModelForm):
    SELECT_TYPE_COMPLAINT = (
        (None, '-- Select type of complaint --'),
        ('Burnt bulbs', 'Burnt bulbs/flourescent tubes'),
        ('Dirty whiteboard', 'Dirty whiteboard (Permanent marker used)'),
        ('Dysfunctional ethernet port', 'Dysfunctional ethernet ports'),
        ('Dysfunctional sockets', 'Dysfunctional sockets'),
        ('Environmental noise', 'Environmental noise'),
        ('Naked electrical wires', 'Naked electrical wires'),
        ('No seats', 'No seats'),
        ('Poor lighting', 'Poor lighting'),
        ('Unfavorable temperature', 'Unfavorable temperature i.e. too cold/hot'),
    )

    complaint = forms.ChoiceField(widget=forms.Select(attrs={
            'type': 'select', 'class': 'mb-0',
        }),
        choices=SELECT_TYPE_COMPLAINT,
        label='Complaints', 
    )
    description = forms.CharField(widget=forms.Textarea(attrs={
            'type': 'text', 'class': 'mb-0', 'placeholder': 'Provide more details about your complaints/approvals about this room/hall ...',
        }),
        help_text='What are your complaints or what you love about this lecture hall/room.',   
    )
    rate_score = forms.CharField(widget=forms.NumberInput(attrs={
            'type': 'number', 'class': 'mb-0', 'min': 0, 'max': 5,
        }),
        help_text='How do you rate this hall?',
        label='Rating',    
    )

    class Meta:
        model = Feedback
        fields = ['complaint', 'description', 'rate_score']


# Edit forms

class EditScheduledLectureForm(forms.ModelForm):
    lecture_date = forms.DateField(widget=forms.DateInput(attrs={
            'type': 'date', 'class': 'mb-0',
        }),
        help_text='Schedule a date for this lecture',    
    )
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={
            'type': 'time', 'class': 'mb-0',
        }),
        help_text='At what time will this lecture begin?',
        label='Schedule start time',
    )
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={
            'type': 'time', 'class': 'mb-0',
        }),
        help_text='At what time will this lecture end?',
        label='Schedule end time',
    )
    recurrence_pattern = forms.ChoiceField(widget=forms.Select(attrs={
            'type': 'select', 'class': 'mb-0',
        }),
        help_text='Schedule lecture none, daily, weekly or monthly',
        label='Recurrence mode',
        choices=(
            ('none', 'None'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ),
    )
    recurrence_end_type = forms.ChoiceField(widget=forms.Select(attrs={
            'class': 'mb-0',
        }),
        choices=(
            ('count', 'By Count'),
            ('date', 'By Date'),
        ),
        required=False,
        label='End Condition'
    )
    recurrence_count = forms.IntegerField(widget=forms.NumberInput(attrs={
            'class': 'mb-0', 'min': 1,
        }),
        required=False,
        label='Occurrences'
    )
    recurrence_end_date = forms.DateField(widget=forms.DateInput(attrs={
            'type': 'date', 'class': 'mb-0',
        }),
        required=False,
        label='End Date'
    )

    class Meta:
        model = Lecture
        fields = ['lecture_date', 'start_time', 'end_time', 'recurrence_pattern', 'recurrence_end_type', 'recurrence_count', 'recurrence_end_date']


class ScheduleLectureForm(forms.ModelForm):
    lecture_date = forms.DateField(widget=forms.DateInput(attrs={
            'type': 'date', 'class': 'mb-0',
        }),
        help_text='Schedule a date for this lecture',    
    )
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={
            'type': 'time', 'class': 'mb-0',
        }),
        help_text='At what time will this lecture begin?',
        label='Schedule start time',
    )
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={
            'type': 'time', 'class': 'mb-0',
        }),
        help_text='At what time will this lecture end?',
        label='Schedule end time',
    )
    recurrence_pattern = forms.ChoiceField(widget=forms.Select(attrs={
            'type': 'select', 'class': 'mb-0',
        }),
        help_text='Schedule lecture none, daily, weekly or monthly',
        label='Recurrence mode',
        choices=(
            ('none', 'None'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ),
    )
    recurrence_end_type = forms.ChoiceField(widget=forms.Select(attrs={
            'class': 'mb-0',
        }),
        choices=(
            ('count', 'By Count'),
            ('date', 'By Date'),
        ),
        required=False,
        label='End Condition'
    )
    recurrence_count = forms.IntegerField(widget=forms.NumberInput(attrs={
            'class': 'mb-0', 'min': 1,
        }),
        required=False,
        label='Occurrences'
    )
    recurrence_end_date = forms.DateField(widget=forms.DateInput(attrs={
            'type': 'date', 'class': 'mb-0',
        }),
        required=False,
        label='End Date'
    )

    class Meta:
        model = Lecture
        fields = ['lecture_date', 'start_time', 'end_time', 'recurrence_pattern', 'recurrence_end_type', 'recurrence_count', 'recurrence_end_date']

    def __init__(self, *args, **kwargs):
        self.lecturer = kwargs.pop('lecturer', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        lecture_date = cleaned_data.get('lecture_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        lecturer = self.lecturer # Use the lecturer passed during initialization

        if not lecturer:
            raise forms.ValidationError("Lecturer information is missing.")

        # Check for overlapping lectures for the same lecturer
        conflicting_lectures = Lecture.objects.filter(
            lecturer=lecturer,
            lecture_date=lecture_date,
            start_time__lt=end_time,
            end_time__gt=start_time
        )
        if self.instance and self.instance.pk:
            conflicting_lectures = conflicting_lectures.exclude(pk=self.instance.pk)

        if conflicting_lectures.exists():
            raise forms.ValidationError(
                "You have another lecture scheduled at this time."
            )

        # Check for overlapping personal events for the same lecturer
        conflicting_personal_events = FacultyPersonalEvent.objects.filter(
            faculty=lecturer, # Filter by faculty object directly
            start_date__date=lecture_date,
            start_date__time__lt=end_time,
            end_date__time__gt=start_time
        )

        if conflicting_personal_events.exists():
            raise forms.ValidationError(
                "You have a personal event scheduled at this time."
            )

        # Check for overlapping meetings for the same lecturer
        conflicting_meetings = MeetingRequest.objects.filter(
            lecturer=lecturer, # Filter by lecturer object directly
            start_time__date=lecture_date,
            start_time__time__lt=end_time,
            end_time__time__gt=start_time,
            status='approved'
        )

        if conflicting_meetings.exists():
            raise forms.ValidationError(
                "You have a meeting scheduled at this time."
            )

        return cleaned_data


class StudentPersonalEventForm(forms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={
        'type': 'text', 'class': 'form-control', 'placeholder': 'Event Title'
    }))
    description = forms.CharField(widget=forms.Textarea(attrs={
        'type': 'text', 'class': 'form-control', 'rows': 3, 'placeholder': 'Event Description (Optional)'
    }), required=False)
    priority = forms.ChoiceField(
        choices=(('low', 'Low'), ('medium', 'Medium'), ('high', 'High')),
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Priority',
    )
    start_date = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))
    end_date = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))
    recurrence_pattern = forms.ChoiceField(widget=forms.Select(attrs={
        'class': 'form-control'
    }), choices=(
        ('none', 'None'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ), initial='none')

    recurrence_end_type = forms.ChoiceField(widget=forms.Select(attrs={
        'class': 'form-control'
    }), choices=(
        ('count', 'By Count'),
        ('date', 'By Date'),
    ), required=False)

    recurrence_count = forms.IntegerField(widget=forms.NumberInput(attrs={
        'class': 'form-control', 'min': 1
    }), required=False)

    recurrence_end_date = forms.DateField(widget=forms.DateInput(attrs={
        'type': 'date', 'class': 'form-control'
    }), required=False)

    class Meta:
        model = StudentPersonalEvent
        fields = ['title', 'description', 'priority', 'start_date', 'end_date',
                  'recurrence_pattern', 'recurrence_end_type', 'recurrence_count', 'recurrence_end_date']

    def __init__(self, *args, **kwargs):
        self.student_instance = kwargs.pop('student_instance', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        # Ensure student instance is available from the request or form initialization
        student = self.student_instance
        if not student and self.instance.pk: # If updating, get student from existing instance
            student = self.instance.student
        
        if not student:
            raise forms.ValidationError("Student information is missing for conflict check.")

        if start_date and end_date:
            if start_date >= end_date:
                raise forms.ValidationError("End date must be after start date.")

            # Check for overlapping personal events for the same student
            conflicting_personal_events = StudentPersonalEvent.objects.filter(
                student=student,
                start_date__lt=end_date,
                end_date__gt=start_date
            )
            if self.instance and self.instance.pk:
                conflicting_personal_events = conflicting_personal_events.exclude(pk=self.instance.pk)

            if conflicting_personal_events.exists():
                raise forms.ValidationError(
                    "You have another personal event scheduled at this time."
                )

            # Check for overlapping lectures for the same student
            conflicting_lectures = Lecture.objects.filter(
                unit_name__registeredunit__student=student,
                lecture_date=start_date.date(),
                start_time__lt=end_date.time(),
                end_time__gt=start_date.time()
            )

            if conflicting_lectures.exists():
                raise forms.ValidationError(
                    "You have a lecture scheduled at this time."
                )

            # Check for overlapping meetings for the same student
            conflicting_meetings = MeetingRequest.objects.filter(
                student=student,
                start_time__lt=end_date,
                end_time__gt=start_date,
                status='approved'
            )

            if conflicting_meetings.exists():
                raise forms.ValidationError(
                    "You have an approved meeting scheduled at this time."
                )

        return cleaned_data

class FacultyPersonalEventForm(forms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={
        'type': 'text', 'class': 'form-control', 'placeholder': 'Event Title'
    }))
    description = forms.CharField(widget=forms.Textarea(attrs={
        'type': 'text', 'class': 'form-control', 'rows': 3, 'placeholder': 'Event Description (Optional)'
    }), required=False)
    priority = forms.ChoiceField(
        choices=(('low', 'Low'), ('medium', 'Medium'), ('high', 'High')),
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Priority',
    )
    start_date = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))
    end_date = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))
    recurrence_pattern = forms.ChoiceField(widget=forms.Select(attrs={
        'class': 'form-control'
    }), choices=(
        ('none', 'None'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ), initial='none')

    recurrence_end_type = forms.ChoiceField(widget=forms.Select(attrs={
        'class': 'form-control'
    }), choices=(
        ('count', 'By Count'),
        ('date', 'By Date'),
    ), required=False)

    recurrence_count = forms.IntegerField(widget=forms.NumberInput(attrs={
        'class': 'form-control', 'min': 1
    }), required=False)

    recurrence_end_date = forms.DateField(widget=forms.DateInput(attrs={
        'type': 'date', 'class': 'form-control'
    }), required=False)

    class Meta:
        model = FacultyPersonalEvent
        fields = ['title', 'description', 'priority', 'start_date', 'end_date', 'recurrence_pattern', 'recurrence_end_type', 'recurrence_count', 'recurrence_end_date']

    def __init__(self, *args, **kwargs):
        self.faculty_instance = kwargs.pop('faculty_instance', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        faculty = self.faculty_instance
        if not faculty and self.instance.pk:
            faculty = self.instance.faculty
        
        if not faculty:
            raise forms.ValidationError("Faculty information is missing for conflict check.")

        if start_date and end_date:
            if start_date >= end_date:
                raise forms.ValidationError("End date must be after start date.")

            # Check for overlapping personal events for the same faculty
            conflicting_personal_events = FacultyPersonalEvent.objects.filter(
                faculty=faculty,
                start_date__lt=end_date,
                end_date__gt=start_date
            )
            if self.instance and self.instance.pk:
                conflicting_personal_events = conflicting_personal_events.exclude(pk=self.instance.pk)

            if conflicting_personal_events.exists():
                raise forms.ValidationError(
                    "You have another personal event scheduled at this time."
                )

            # Check for overlapping lectures for the same faculty
            conflicting_lectures = Lecture.objects.filter(
                lecturer=faculty,
                lecture_date=start_date.date(),
                start_time__lt=end_date.time(),
                end_time__gt=start_date.time()
            )

            if conflicting_lectures.exists():
                raise forms.ValidationError(
                    "You have a lecture scheduled at this time."
                )

            # Check for overlapping meetings for the same faculty
            conflicting_meetings = MeetingRequest.objects.filter(
                lecturer=faculty,
                start_time__lt=end_date,
                end_time__gt=start_date,
                status='approved'
            )

            if conflicting_meetings.exists():
                raise forms.ValidationError(
                    "You have an approved meeting scheduled at this time."
                )

        return cleaned_data


class MeetingRequestForm(forms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={
        'type': 'text', 'class': 'form-control', 'placeholder': 'Meeting Title'
    }))
    description = forms.CharField(widget=forms.Textarea(attrs={
        'type': 'text', 'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for meeting (Optional)'
    }), required=False)
    start_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))
    end_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))
    location = forms.CharField(widget=forms.TextInput(attrs={
        'type': 'text', 'class': 'form-control', 'placeholder': 'Proposed Location'
    }))

    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = MeetingRequest
        fields = ['title', 'description', 'start_time', 'end_time', 'location']

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        student = self.student

        if not student:
            raise forms.ValidationError("Student information is missing.")

        # Check for overlapping personal events for the same student
        conflicting_personal_events = StudentPersonalEvent.objects.filter(
            student=student,
            start_date__lt=end_time,
            end_date__gt=start_time
        )
        if self.instance and self.instance.pk:
            conflicting_personal_events = conflicting_personal_events.exclude(pk=self.instance.pk)

        if conflicting_personal_events.exists():
            raise forms.ValidationError(
                "You have another personal event scheduled at this time."
            )

        # Check for overlapping lectures for the same student
        conflicting_lectures = Lecture.objects.filter(
            unit_name__registeredunit__student=student,
            lecture_date=start_time.date(),
            start_time__lt=end_time.time(),
            end_time__gt=start_time.time()
        )

        if conflicting_lectures.exists():
            raise forms.ValidationError(
                "You have a lecture scheduled at this time."
            )

        # Check for overlapping meetings for the same student
        conflicting_meetings = MeetingRequest.objects.filter(
            student=student,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status='approved'
        )
        if self.instance and self.instance.pk:
            conflicting_meetings = conflicting_meetings.exclude(pk=self.instance.pk)

        if conflicting_meetings.exists():
            raise forms.ValidationError(
                "You have another meeting scheduled at this time."
            )

        return cleaned_data

class EditMeetingRequestForm(forms.ModelForm):
    start_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))
    end_time = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))
    location = forms.CharField(widget=forms.TextInput(attrs={
        'type': 'text', 'class': 'form-control', 'placeholder': 'Proposed Location'
    }))

    class Meta:
        model = MeetingRequest
        fields = ['start_time', 'end_time', 'location']