from accounts.models import Student, Faculty
from django.db import models

import uuid # Added for unique ID generation

class BookedUnit(models.Model):
    """ These are records of units assigned to a lecturer each semester. """
    id = models.CharField(max_length=30, primary_key=True, unique=True, editable=False)
    lecturer = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    students_course = models.CharField(max_length=50, blank=False)
    course_name = models.CharField(max_length=80, blank=False)
    year_of_study = models.CharField(max_length=10, blank=False)
    semester = models.CharField(max_length=1, blank=False)
    booking_date = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.course_name
    
    class Meta:
        ordering = ['course_name', 'lecturer']
        verbose_name_plural = 'Booked units'

class RegisteredUnit(models.Model):
    """ These are records for units a student has registered in a given semester. """
    id = models.CharField(max_length=30, primary_key=True, unique=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, editable=False)
    unit = models.ForeignKey(BookedUnit, on_delete=models.CASCADE)
    is_registered = models.BooleanField(default=False, editable=False)
    date_registered = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['unit', 'student']
        verbose_name_plural = 'Registered units'
    
    def __str__(self) -> str:
        return self.student

class Lecture(models.Model):
    """ This db table stores records of all scheduled lectures. """
    id = models.CharField(max_length=30, primary_key=True, unique=True, editable=False)
    lecturer = models.ForeignKey(Faculty, on_delete=models.CASCADE, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, editable=False)
    lecture_hall = models.ForeignKey('LectureHall', on_delete=models.CASCADE, editable=False, null=True, db_column='Venue')
    unit_name = models.ForeignKey(BookedUnit, on_delete=models.CASCADE)
    lecture_date = models.DateField(null=False, blank=False)
    start_time = models.TimeField(null=False, blank=False, db_column='Scheduled start time')    # lecture should start at this time
    end_time = models.TimeField(null=False, blank=False, db_column='Scheduled end time')     # lecture should end at this time
    recurrence_pattern = models.CharField(max_length=10, blank=False)
    total_students = models.PositiveIntegerField(default=0, editable=False)     # approximate no. of students expected to attend the lecture.
    is_attending = models.BooleanField(default=False)   # is the student attending the lecture?
    is_taught = models.BooleanField(default=False, editable=False)  # was the class taught or it "bounced".
    date_scheduled = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['lecturer', 'lecture_hall', '-date_scheduled']
        verbose_name_plural = 'Scheduled lectures'


class LectureHall(models.Model):
    """ This db table stores records of all available lecture halls in the entire institution. """
    id = models.CharField(max_length=30, primary_key=True, unique=True, editable=False)
    academic_block = models.CharField(max_length=20, blank=False)
    hall_no = models.CharField(max_length=5, unique=True, blank=False)
    seating_capacity = models.PositiveIntegerField(default=0)
    floor = models.CharField(max_length=7, blank=False)
    rating = models.PositiveIntegerField(default=0, editable=False)
    image = models.ImageField(upload_to='Lecture-Halls/img/', default='lecture-hall.jpg')
    date_created = models.DateTimeField(auto_now_add=True)
    date_edited = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.hall_no
    
    class Meta:
        ordering = ['academic_block', 'hall_no']
        verbose_name_plural = 'Lecture halls'

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

class Notification(models.Model):
    id = models.CharField(max_length=30, primary_key=True, unique=True, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', null=True)
    message = models.CharField(max_length=255)
    
    # Generic Foreign Key
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    #object_id = models.CharField(max_length=50)
    object_id = models.CharField(max_length=50, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    is_read = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.message
    
    class Meta:
        ordering = ['-date_created']
        verbose_name_plural = 'Notifications'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        super().save(*args, **kwargs)
    
class Feedback(models.Model):
    """ These are records of students feedback about lecture halls assigned for a given lecture. """
    id = models.CharField(max_length=30, primary_key=True, unique=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, editable=False)
    lecture_hall = models.ForeignKey(LectureHall, on_delete=models.CASCADE, editable=False)
    complaint = models.CharField(max_length=30, blank=False)
    description = models.TextField()
    rate_score = models.PositiveIntegerField(default=0)
    date_posted = models.DateTimeField(auto_now_add=True)
    date_edited = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'{self.lecture_hall}'
    
    class Meta:
        ordering = ['lecture_hall', '-date_posted']
        verbose_name_plural = 'Feedback'


class StudentPersonalEvent(models.Model):
    """ Stores personal events or to-do items for a student. """
    id = models.CharField(max_length=30, primary_key=True, unique=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['start_date']
        verbose_name_plural = 'Student Personal Events'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        super().save(*args, **kwargs)


class FacultyPersonalEvent(models.Model):
    """ Stores personal events or to-do items for a faculty member. """
    id = models.CharField(max_length=30, primary_key=True, unique=True, editable=False)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['start_date']
        verbose_name_plural = 'Faculty Personal Events'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        super().save(*args, **kwargs)


class MeetingRequest(models.Model):
    """ Stores meeting requests from students to lecturers. """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('modified', 'Modified'),
    )

    id = models.CharField(max_length=30, primary_key=True, unique=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    lecturer = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Meeting request from {self.student} to {self.lecturer} re: {self.title}"

    class Meta:
        ordering = ['start_time']
        verbose_name_plural = 'Meeting Requests'
