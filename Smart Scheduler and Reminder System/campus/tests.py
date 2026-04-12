from django.test import TestCase
from django.utils import timezone
from accounts.models import User, Student, Faculty
from .models import Course, BookedUnit, FacultyPersonalEvent, MeetingRequest
import uuid

class CampusLogicTests(TestCase):
    def setUp(self):
        # 1. 创建教师
        self.u_teacher = User.objects.create_user(
            username='teacher1', 
            email='t1@test.com',
            password='password123',
            first_name='John',
            last_name='Doe',
            dob='1980-01-01',
            gender='Male',
            mobile_no='+1234567890'
        )
        self.faculty = Faculty.objects.create(
            staff=self.u_teacher, 
            school='SCI', 
            department='CS', 
            position='Lecturer'
        )
        
        # 2. 创建学生
        self.u_student = User.objects.create_user(
            username='student1', 
            email='s1@test.com',
            password='password123',
            first_name='Jane',
            last_name='Smith',
            dob='2002-01-01',
            gender='Female',
            mobile_no='+1098765432'
        )
        self.student = Student.objects.create(
            student_name=self.u_student, 
            reg_no='REG/001', 
            school='SCI', 
            department='CS', 
            year='1', 
            semester='1', 
            programme='CS', 
            course='CS'
        )
        
        # 3. 创建课程
        self.course = Course.objects.create(name='Software Engineering', code='CS301')

    def test_course_booking(self):
        """测试教师预约课程单元"""
        booked = BookedUnit.objects.create(
            lecturer=self.faculty,
            course=self.course,
            students_course='CS',
            year_of_study='3',
            semester='1'
        )
        self.assertEqual(booked.course.name, 'Software Engineering')

    def test_meeting_request_workflow(self):
        """测试学生向教师发起会议请求并修改状态"""
        start = timezone.now() + timezone.timedelta(days=1)
        end = start + timezone.timedelta(hours=1)
        
        meeting = MeetingRequest.objects.create(
            student=self.student,
            lecturer=self.faculty,
            title='Project Discussion',
            start_time=start,
            end_time=end,
            location='Office 101'
        )
        
        self.assertEqual(meeting.status, 'pending')
        
        # 模拟教师批准
        meeting.status = 'approved'
        meeting.save()
        self.assertEqual(MeetingRequest.objects.get(id=meeting.id).status, 'approved')

    def test_faculty_personal_event(self):
        """测试教职员工个人事件的创建"""
        event = FacultyPersonalEvent.objects.create(
            faculty=self.faculty,
            title='Research Seminar',
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(hours=2)
        )
        self.assertEqual(event.title, 'Research Seminar')

from django.core.exceptions import ValidationError

class ConflictDetectionTests(TestCase):
    def setUp(self):
        self.u_teacher = User.objects.create_user(
            username='conflictt', email='ct@test.com', dob='1980-01-01', gender='Male'
        )
        self.faculty = Faculty.objects.create(staff=self.u_teacher, school='SCI', department='CS', position='Lecturer')

    def test_personal_event_time_conflict(self):
        """验证同一教师在重叠时间内创建事件会失败"""
        start = timezone.now()
        end = start + timezone.timedelta(hours=2)

        # 第一个事件
        FacultyPersonalEvent.objects.create(
            faculty=self.faculty, title='Event 1', start_date=start, end_date=end
        )

        # 第二个重叠事件
        overlapping_event = FacultyPersonalEvent(
            faculty=self.faculty, title='Event 2', 
            start_date=start + timezone.timedelta(hours=1), 
            end_date=end + timezone.timedelta(hours=1)
        )

        with self.assertRaises(ValidationError):
            overlapping_event.save()


from .tasks import auto_judge_event_statuses
from .models import Lecture, StudentPersonalEvent

class EventStatusJudgementTests(TestCase):
    def setUp(self):
        # Create student and teacher
        self.u_teacher, _ = User.objects.get_or_create(
            username='judge_teacher', 
            defaults={'email': 'jt@test.com', 'dob': '1980-01-01', 'gender': 'Male'}
        )
        self.faculty, _ = Faculty.objects.get_or_create(
            staff=self.u_teacher, 
            defaults={'school': 'SCI', 'department': 'CS', 'position': 'Lecturer'}
        )
        
        self.u_student, _ = User.objects.get_or_create(
            username='judge_student', 
            defaults={'email': 'js@test.com', 'dob': '2002-01-01', 'gender': 'Female'}
        )
        self.student, _ = Student.objects.get_or_create(
            student_name=self.u_student, 
            defaults={'reg_no': 'REG/002', 'school': 'SCI', 'department': 'CS', 'year': '1', 'semester': '1', 'programme': 'CS', 'course': 'CS'}
        )
        
        self.course, _ = Course.objects.get_or_create(name='Automated Testing', defaults={'code': 'CS404'})
        self.booked_unit, _ = BookedUnit.objects.get_or_create(
            lecturer=self.faculty, 
            course=self.course, 
            defaults={'students_course': 'CS', 'year_of_study': '1', 'semester': '1'}
        )

    def test_auto_judge_lecture_completed(self):
        """Verify lecture is marked as completed if total_students > 0"""
        past_date = timezone.now().date() - timezone.timedelta(days=1)
        lecture = Lecture.objects.create(
            id='test_lecture_comp',
            lecturer=self.faculty,
            unit_name=self.booked_unit,
            lecture_date=past_date,
            start_time='10:00:00',
            end_time='12:00:00',
            recurrence_pattern='None',
            status='scheduled',
            total_students=1
        )
        
        auto_judge_event_statuses()
        
        lecture.refresh_from_db()
        self.assertEqual(lecture.status, 'completed')

    def test_auto_judge_lecture_missed(self):
        """Verify lecture is marked as missed if total_students == 0"""
        past_date = timezone.now().date() - timezone.timedelta(days=1)
        lecture = Lecture.objects.create(
            id='test_lecture_miss',
            lecturer=self.faculty,
            unit_name=self.booked_unit,
            lecture_date=past_date,
            start_time='10:00:00',
            end_time='12:00:00',
            recurrence_pattern='None',
            status='scheduled',
            total_students=0
        )
        
        auto_judge_event_statuses()
        
        lecture.refresh_from_db()
        self.assertEqual(lecture.status, 'missed')

    def test_auto_judge_personal_event_completed(self):
        """Verify personal event is marked as completed if signed in"""
        past_start = timezone.now() - timezone.timedelta(hours=2)
        past_end = timezone.now() - timezone.timedelta(hours=1)
        
        event = StudentPersonalEvent.objects.create(
            id='test_personal_comp',
            student=self.student,
            title='Study Session',
            start_date=past_start,
            end_date=past_end,
            is_signed_in=True,
            status='pending'
        )
        
        auto_judge_event_statuses()
        
        event.refresh_from_db()
        self.assertEqual(event.status, 'completed')

    def test_auto_judge_personal_event_missed(self):
        """Verify personal event is marked as missed if not signed in"""
        past_start = timezone.now() - timezone.timedelta(hours=2)
        past_end = timezone.now() - timezone.timedelta(hours=1)
        
        event = StudentPersonalEvent.objects.create(
            id='test_personal_miss',
            student=self.student,
            title='Study Session',
            start_date=past_start,
            end_date=past_end,
            is_signed_in=False,
            status='pending'
        )
        
        auto_judge_event_statuses()
        
        event.refresh_from_db()
        self.assertEqual(event.status, 'missed')

class PersonalReportTests(TestCase):
    def setUp(self):
        self.u_student = User.objects.create_user(
            username='report_student', email='rs@test.com', dob='2002-01-01', gender='Female', password='password123',
            is_student=True
        )
        self.student = Student.objects.create(student_name=self.u_student, reg_no='REG/REP01', school='SCI', department='CS', year='1', semester='1', programme='CS', course='CS')
        
    def test_personal_report_view_status_code(self):
        """Verify the personal report view returns 200 for a logged-in student"""
        login_success = self.client.login(email='rs@test.com', password='password123')
        self.assertTrue(login_success)
        # Use the full URL including /campus/u/ prefix as seen in src/urls.py
        response = self.client.get('/campus/u/personal-report/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/reports.html')

    def test_personal_report_counts(self):
        """Verify the counts in the personal report are correct"""
        # Create some events at different times to avoid validation error
        now = timezone.now()
        StudentPersonalEvent.objects.create(
            id='rep_ev1', student=self.student, title='E1', 
            start_date=now + timezone.timedelta(hours=1), 
            end_date=now + timezone.timedelta(hours=2),
            status='completed', is_signed_in=True
        )
        StudentPersonalEvent.objects.create(
            id='rep_ev2', student=self.student, title='E2', 
            start_date=now + timezone.timedelta(hours=3), 
            end_date=now + timezone.timedelta(hours=4),
            status='missed', is_signed_in=False
        )
        
        login_success = self.client.login(email='rs@test.com', password='password123')
        self.assertTrue(login_success)
        response = self.client.get('/campus/u/personal-report/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['personal_stats']['completed'], 1)
        self.assertEqual(response.context['personal_stats']['missed'], 1)
        self.assertEqual(response.context['total_completed'], 1)
        self.assertEqual(response.context['total_missed'], 1)

