from accounts.models import Student, Faculty
from django.db import models
from django.core.exceptions import ValidationError
import uuid 

class Course(models.Model):
    """ Defines academic courses offered. """
    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
    name = models.CharField(max_length=80, unique=True, blank=False)
    code = models.CharField(max_length=10, unique=True, blank=False)
    description = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Courses'

class BookedUnit(models.Model):
    """ These are records of units assigned to a lecturer each semester. """
    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
    lecturer = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    students_course = models.CharField(max_length=50, blank=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    year_of_study = models.CharField(max_length=10, blank=False)
    semester = models.CharField(max_length=1, blank=False)
    booking_date = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.course.name
    
    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        self.full_clean()
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['course__name', 'lecturer']
        verbose_name_plural = 'Booked units'

class RegisteredUnit(models.Model):
    """ These are records for units a student has registered in a given semester. """
    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, editable=False)
    unit = models.ForeignKey(BookedUnit, on_delete=models.CASCADE)
    is_registered = models.BooleanField(default=False, editable=False)
    date_registered = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.student)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        self.full_clean()
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['unit', 'student']
        verbose_name_plural = 'Registered units'

class Lecture(models.Model):
    """ This db table stores records of all scheduled lectures. """
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
    )

    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
    lecturer = models.ForeignKey(Faculty, on_delete=models.CASCADE, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, editable=False)
    lecture_hall = models.ForeignKey('LectureHall', on_delete=models.CASCADE, editable=False, null=True, db_column='Venue')
    unit_name = models.ForeignKey(BookedUnit, on_delete=models.CASCADE)
    lecture_date = models.DateField(null=False, blank=False)
    start_time = models.TimeField(null=False, blank=False, db_column='Scheduled start time')
    end_time = models.TimeField(null=False, blank=False, db_column='Scheduled end time')
    recurrence_pattern = models.CharField(max_length=10, blank=False)
    total_students = models.PositiveIntegerField(default=0, editable=False)
    is_attending = models.BooleanField(default=False)
    is_taught = models.BooleanField(default=False, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='scheduled')
    date_scheduled = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def clean(self):
        # 检查教室地点冲突
        if self.lecture_hall and self.lecture_date and self.start_time and self.end_time:
            conflicts = Lecture.objects.filter(
                lecture_hall=self.lecture_hall,
                lecture_date=self.lecture_date,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time
            )
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            if conflicts.exists():
                raise ValidationError(f"地点冲突：该教室 {self.lecture_hall} 在指定时间内已有课程安排。")

    def save(self, *args, **kwargs):
        self.full_clean() # 执行验证
        if not self.id:
            self.id = str(uuid.uuid4())
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['lecturer', 'lecture_hall', '-date_scheduled']
        verbose_name_plural = 'Scheduled lectures'


class LectureHall(models.Model):
    """ This db table stores records of all available lecture halls in the entire institution. """
    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
    academic_block = models.CharField(max_length=20, blank=False)
    hall_no = models.CharField(max_length=5, unique=True, blank=False)
    seating_capacity = models.PositiveIntegerField(default=0)
    floor = models.CharField(max_length=7, blank=False)
    rating = models.PositiveIntegerField(default=0, editable=False)
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
    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', null=True)
    message = models.CharField(max_length=255)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
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
        self.full_clean()
        super().save(*args, **kwargs)
    
class Feedback(models.Model):
    """ These are records of students feedback about lecture halls assigned for a given lecture. """
    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
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

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = str(uuid.uuid4())
        self.full_clean()
        super().save(*args, **kwargs)


class StudentPersonalEvent(models.Model):
    """ Stores personal events or to-do items for a student. """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
    )

    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    sent_reminders = models.CharField(max_length=100, blank=True, help_text="Comma-separated list of sent reminder times, e.g., '60min,15min'")
    is_signed_in = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def clean(self):
        if hasattr(self, 'student') and self.start_date and self.end_date:
            conflicts = StudentPersonalEvent.objects.filter(
                student=self.student,
                start_date__lt=self.end_date,
                end_date__gt=self.start_date
            )
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            if conflicts.exists():
                raise ValidationError("时间冲突：该时间段内已有其他个人日程。")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.id:
            self.id = str(uuid.uuid4())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['start_date']
        verbose_name_plural = 'Student Personal Events'


class FacultyPersonalEvent(models.Model):
    """ Stores personal events or to-do items for a faculty member. """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
    )

    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    sent_reminders = models.CharField(max_length=100, blank=True, help_text="Comma-separated list of sent reminder times, e.g., '60min,15min'")
    is_signed_in = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def clean(self):
        if hasattr(self, 'faculty') and self.start_date and self.end_date:
            conflicts = FacultyPersonalEvent.objects.filter(
                faculty=self.faculty,
                start_date__lt=self.end_date,
                end_date__gt=self.start_date
            )
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            if conflicts.exists():
                raise ValidationError("时间冲突：该时间段内已有其他工作安排。")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.id:
            self.id = str(uuid.uuid4())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['start_date']
        verbose_name_plural = 'Faculty Personal Events'


class MeetingRequest(models.Model):
    """ Stores meeting requests from students to lecturers. """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('modified', 'Modified'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
    )

    id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    lecturer = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=200)
    is_signed_in = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.start_time and self.end_time:
            # 检查会议室/地点冲突
            loc_conflicts = MeetingRequest.objects.filter(
                location=self.location,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
                status='approved'
            )
            # 检查教师或学生时间冲突
            user_conflicts = MeetingRequest.objects.filter(
                models.Q(student=self.student) | models.Q(lecturer=self.lecturer),
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
                status='approved'
            )
            if self.pk:
                loc_conflicts = loc_conflicts.exclude(pk=self.pk)
                user_conflicts = user_conflicts.exclude(pk=self.pk)
            
            if loc_conflicts.exists():
                raise ValidationError(f"地点冲突：该地点 {self.location} 已被其他会议批准使用。")
            if user_conflicts.exists():
                raise ValidationError("人员冲突：该时间段内教师或学生已有批准的会议。")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.id:
            self.id = str(uuid.uuid4())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Meeting request from {self.student} to {self.lecturer} re: {self.title}"

    class Meta:
        ordering = ['start_time']
        verbose_name_plural = 'Meeting Requests'
