from .models import BookedUnit, Feedback, Lecture, RegisteredUnit, StudentPersonalEvent, MeetingRequest, LectureHall, FacultyPersonalEvent
from accounts.models import Faculty
from django import forms

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

class LecturerUnitsBookingForm(forms.ModelForm):
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
    
    course_name = forms.CharField(widget=forms.TextInput(attrs={
            'type': 'select', 'class': 'mb-0',
        }),
        label='Unit name',
        help_text='Enter the name of the unit (<b>Enter course code & course title</b>)<br>'
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
        # Filter all faculty staff in the OneToOneField dropdown
        self.fields['lecturer'].queryset = Faculty.objects.filter()

    class Meta:
        model = BookedUnit
        fields = ['lecturer', 'course_name', 'students_course',  'year_of_study', 'semester']

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
    SELECT_RECURRENCE_PATTERN = (
        (None, '-- Select one choice --'),
        ('once', 'Once'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    )

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
            'type': 'text', 'class': 'mb-0',
        }),
        help_text='Schedule lecture once, daily or weekly',
        label='Recurrence mode',
        choices=SELECT_RECURRENCE_PATTERN,
    )

    class Meta:
        model = Lecture
        fields = ['lecture_date', 'start_time', 'end_time', 'recurrence_pattern']


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
        help_text='Schedule lecture once, daily or weekly',
        label='Recurrence mode',
        choices=(
            (None, '-- Select one choice --'),
            ('once', 'Once'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
        ),
    )

    class Meta:
        model = Lecture
        exclude = ['unit_name', 'lecture_hall', 'is_attending', 'total_students']

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
    start_date = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))
    end_date = forms.DateTimeField(widget=forms.DateTimeInput(attrs={
        'type': 'datetime-local', 'class': 'form-control'
    }))

    class Meta:
        model = StudentPersonalEvent
        fields = ['title', 'description', 'start_date', 'end_date']

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        user = self.instance.user

        # Check for overlapping personal events
        conflicting_personal_events = StudentPersonalEvent.objects.filter(
            user=user,
            start_date__lt=end_date,
            end_date__gt=start_date
        ).exclude(pk=self.instance.pk)

        if conflicting_personal_events.exists():
            raise forms.ValidationError(
                "You have another personal event scheduled at this time."
            )

        # Check for overlapping lectures
        conflicting_lectures = Lecture.objects.filter(
            unit_name__registeredunit__student=user.student,
            lecture_date=start_date.date(),
            start_time__lt=end_date.time(),
            end_time__gt=start_date.time()
        )

        if conflicting_lectures.exists():
            raise forms.ValidationError(
                "You have a lecture scheduled at this time."
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