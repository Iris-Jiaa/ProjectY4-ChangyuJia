"""
campus/tests.py
Unit & integration tests for the campus module, covering:
  1.  Core model operations (Course, BookedUnit, LectureHall, Holiday)
  2.  Conflict detection  (Lecture venue, FacultyPersonalEvent, StudentPersonalEvent, MeetingRequest)
  3.  MeetingRequest – full 7-state status workflow
  4.  Automated event-status judgement (Celery task)
  5.  RBAC – role-based access control on key URL endpoints
  6.  View tests – personal report, admin course list, bidirectional calendar API
  7.  Notification model
"""

from django.test import TestCase, Client
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.urls import reverse

from accounts.models import User, Student, Faculty
from .models import (
    Course, BookedUnit, LectureHall, Lecture,
    Holiday, MeetingRequest,
    FacultyPersonalEvent, StudentPersonalEvent,
    Notification,
)
from .tasks import auto_judge_event_statuses
from django.contrib.contenttypes.models import ContentType


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def make_user(username, email, **kw):
    defaults = dict(password='password123', first_name='A', last_name='B',
                    mobile_no='+10000000000', dob='1990-01-01', gender='Male')
    defaults.update(kw)
    return User.objects.create_user(username=username, email=email, **defaults)


def make_faculty(username, email, position='Lecturer'):
    u = make_user(username, email)
    f = Faculty.objects.create(staff=u, school='SCI', department='CS', position=position)
    return u, f


def make_student(username, email, reg_no):
    u = make_user(username, email, gender='Female', is_student=True)
    s = Student.objects.create(
        student_name=u, reg_no=reg_no,
        school='SCI', department='CS',
        year='1', semester='1',
        programme='CS', course='CS',
    )
    return u, s


def make_hall(hall_no='H01', capacity=50):
    h = LectureHall(
        academic_block='A', hall_no=hall_no,
        seating_capacity=capacity, floor='1',
    )
    h.id = hall_no          # simple id so we don't need uuid
    h.save()
    return h


# ---------------------------------------------------------------------------
# 1. Core model tests
# ---------------------------------------------------------------------------

class CourseModelTests(TestCase):

    def test_create_course(self):
        """Course can be created with name and code."""
        c = Course.objects.create(name='Data Structures', code='CS101')
        self.assertEqual(str(c), 'Data Structures')

    def test_duplicate_course_code_raises(self):
        """Duplicate course code raises an integrity error."""
        Course.objects.create(name='Course A', code='DUP01')
        with self.assertRaises(Exception):
            Course.objects.create(name='Course B', code='DUP01')

    def test_booked_unit_links_lecturer_and_course(self):
        """BookedUnit correctly references lecturer and course."""
        _, fac = make_faculty('lec_bu', 'lec_bu@t.com')
        course = Course.objects.create(name='Algorithms', code='CS201')
        bu = BookedUnit.objects.create(
            lecturer=fac, course=course,
            students_course='CS', year_of_study='2', semester='1',
        )
        self.assertEqual(bu.course.name, 'Algorithms')
        self.assertEqual(str(bu), 'Algorithms')


class HolidayValidationTests(TestCase):

    def test_valid_holiday_saves(self):
        """Holiday with start ≤ end saves without error."""
        h = Holiday.objects.create(
            name='Spring Break',
            start_date='2026-04-01',
            end_date='2026-04-07',
        )
        self.assertEqual(str(h), 'Spring Break (2026-04-01 ~ 2026-04-07)')

    def test_holiday_end_before_start_raises(self):
        """Holiday with end date before start date raises ValidationError."""
        with self.assertRaises(ValidationError):
            Holiday.objects.create(
                name='Bad Holiday',
                start_date='2026-04-10',
                end_date='2026-04-05',
            )


# ---------------------------------------------------------------------------
# 2. Conflict detection tests
# ---------------------------------------------------------------------------

class LectureVenueConflictTests(TestCase):
    """Lecture.clean() must reject two lectures sharing hall + date + overlapping time."""

    def setUp(self):
        _, self.fac = make_faculty('lec_venue', 'lec_venue@t.com')
        course = Course.objects.create(name='Physics', code='PHY101')
        self.bu = BookedUnit.objects.create(
            lecturer=self.fac, course=course,
            students_course='SCI', year_of_study='1', semester='1',
        )
        self.hall = make_hall('H02', 80)

    def _make_lecture(self, lid, start, end):
        return Lecture(
            id=lid, lecturer=self.fac, unit_name=self.bu,
            lecture_hall=self.hall,
            lecture_date='2026-09-01',
            start_time=start, end_time=end,
            recurrence_pattern='none', status='scheduled',
        )

    def test_venue_conflict_raises_validation_error(self):
        """Second lecture at same hall and overlapping time raises ValidationError."""
        lec1 = self._make_lecture('LEC001', '08:00', '10:00')
        lec1.save()

        lec2 = self._make_lecture('LEC002', '09:00', '11:00')
        with self.assertRaises(ValidationError):
            lec2.save()

    def test_non_overlapping_lectures_saved(self):
        """Two lectures in same hall at different times save without error."""
        lec1 = self._make_lecture('LEC003', '08:00', '10:00')
        lec1.save()

        lec2 = self._make_lecture('LEC004', '10:00', '12:00')
        lec2.save()   # should not raise
        self.assertEqual(Lecture.objects.filter(lecture_hall=self.hall).count(), 2)

    def test_different_halls_no_conflict(self):
        """Same time slot in different halls is allowed."""
        hall2 = make_hall('H03', 60)
        lec1 = self._make_lecture('LEC005', '08:00', '10:00')
        lec1.save()

        lec2 = Lecture(
            id='LEC006', lecturer=self.fac, unit_name=self.bu,
            lecture_hall=hall2,
            lecture_date='2026-09-01',
            start_time='08:00', end_time='10:00',
            recurrence_pattern='none', status='scheduled',
        )
        lec2.save()   # different hall → no conflict
        self.assertTrue(Lecture.objects.filter(id='LEC006').exists())


class FacultyPersonalEventConflictTests(TestCase):

    def setUp(self):
        _, self.fac = make_faculty('fac_ev', 'fac_ev@t.com')
        self.start = timezone.now() + timezone.timedelta(hours=1)
        self.end   = self.start + timezone.timedelta(hours=2)

    def test_overlapping_event_raises(self):
        """Second overlapping personal event for same faculty raises ValidationError."""
        FacultyPersonalEvent.objects.create(
            faculty=self.fac, title='Event A',
            start_date=self.start, end_date=self.end,
        )
        overlapping = FacultyPersonalEvent(
            faculty=self.fac, title='Event B',
            start_date=self.start + timezone.timedelta(hours=1),
            end_date=self.end   + timezone.timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            overlapping.save()

    def test_adjacent_events_allowed(self):
        """Event starting exactly when another ends is NOT overlapping."""
        FacultyPersonalEvent.objects.create(
            faculty=self.fac, title='Morning',
            start_date=self.start, end_date=self.end,
        )
        adjacent = FacultyPersonalEvent(
            faculty=self.fac, title='Afternoon',
            start_date=self.end,
            end_date=self.end + timezone.timedelta(hours=2),
        )
        adjacent.save()   # should succeed
        self.assertEqual(FacultyPersonalEvent.objects.filter(faculty=self.fac).count(), 2)


class StudentPersonalEventConflictTests(TestCase):

    def setUp(self):
        _, self.stu = make_student('stu_ev', 'stu_ev@t.com', 'REG/EV01')
        self.start = timezone.now() + timezone.timedelta(hours=3)
        self.end   = self.start + timezone.timedelta(hours=2)

    def test_overlapping_student_event_raises(self):
        """Student cannot create two overlapping personal events."""
        StudentPersonalEvent.objects.create(
            id='SEV001', student=self.stu, title='Study',
            start_date=self.start, end_date=self.end,
        )
        conflict = StudentPersonalEvent(
            id='SEV002', student=self.stu, title='Gym',
            start_date=self.start + timezone.timedelta(hours=1),
            end_date=self.end   + timezone.timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            conflict.save()

    def test_different_students_no_conflict(self):
        """Same time slot for different students is allowed."""
        _, stu2 = make_student('stu_ev2', 'stu_ev2@t.com', 'REG/EV02')
        StudentPersonalEvent.objects.create(
            id='SEV003', student=self.stu, title='Study',
            start_date=self.start, end_date=self.end,
        )
        ev2 = StudentPersonalEvent(
            id='SEV004', student=stu2, title='Study',
            start_date=self.start, end_date=self.end,
        )
        ev2.save()   # different student → allowed
        self.assertTrue(StudentPersonalEvent.objects.filter(id='SEV004').exists())


class MeetingRequestConflictTests(TestCase):

    def setUp(self):
        _, self.fac  = make_faculty('mr_lec', 'mr_lec@t.com')
        _, self.stu  = make_student('mr_stu', 'mr_stu@t.com', 'REG/MR01')
        _, self.stu2 = make_student('mr_stu2', 'mr_stu2@t.com', 'REG/MR02')
        self.start = timezone.now() + timezone.timedelta(days=1)
        self.end   = self.start + timezone.timedelta(hours=1)

    def _approved_meeting(self, mid, student, location='Room 101'):
        m = MeetingRequest(
            id=mid, student=student, lecturer=self.fac,
            title='Discussion', start_time=self.start, end_time=self.end,
            location=location, status='pending',
        )
        m.full_clean()
        # bypass clean() to set approved directly for setup
        MeetingRequest.objects.filter(id=mid).delete()
        m.status = 'approved'
        super(MeetingRequest, m).save()
        return m

    def test_location_conflict_raises(self):
        """Two approved meetings at same location and time conflict."""
        self._approved_meeting('MR001', self.stu, location='Room 101')

        conflict = MeetingRequest(
            student=self.stu2, lecturer=self.fac,
            title='Another', start_time=self.start, end_time=self.end,
            location='Room 101', status='pending',
        )
        # Set FKs manually so clean() runs
        conflict.student_id = self.stu2.id
        conflict.lecturer_id = self.fac.id
        with self.assertRaises(ValidationError):
            conflict.clean()


# ---------------------------------------------------------------------------
# 3. MeetingRequest – 7-state status workflow
# ---------------------------------------------------------------------------

class MeetingRequestWorkflowTests(TestCase):

    def setUp(self):
        _, self.fac = make_faculty('wf_lec', 'wf_lec@t.com')
        _, self.stu = make_student('wf_stu', 'wf_stu@t.com', 'REG/WF01')
        start = timezone.now() + timezone.timedelta(days=2)
        end   = start + timezone.timedelta(hours=1)
        self.meeting = MeetingRequest.objects.create(
            student=self.stu, lecturer=self.fac,
            title='Thesis Chat',
            start_time=start, end_time=end,
            location='Office 5',
        )

    def _set_status(self, status):
        self.meeting.status = status
        MeetingRequest.objects.filter(id=self.meeting.id).update(status=status)

    def test_initial_status_is_pending(self):
        self.assertEqual(self.meeting.status, 'pending')

    def test_approved_status(self):
        self._set_status('approved')
        self.assertEqual(MeetingRequest.objects.get(id=self.meeting.id).status, 'approved')

    def test_rejected_status(self):
        self._set_status('rejected')
        self.assertEqual(MeetingRequest.objects.get(id=self.meeting.id).status, 'rejected')

    def test_modified_status(self):
        self._set_status('modified')
        self.assertEqual(MeetingRequest.objects.get(id=self.meeting.id).status, 'modified')

    def test_cancelled_status(self):
        self._set_status('cancelled')
        self.assertEqual(MeetingRequest.objects.get(id=self.meeting.id).status, 'cancelled')

    def test_completed_status(self):
        self._set_status('completed')
        self.assertEqual(MeetingRequest.objects.get(id=self.meeting.id).status, 'completed')

    def test_missed_status(self):
        self._set_status('missed')
        self.assertEqual(MeetingRequest.objects.get(id=self.meeting.id).status, 'missed')


# ---------------------------------------------------------------------------
# 4. Automated event-status judgement (Celery task logic)
# ---------------------------------------------------------------------------

class EventStatusJudgementTests(TestCase):

    def setUp(self):
        _, self.fac = make_faculty('judge_lec', 'jl@t.com')
        _, self.stu = make_student('judge_stu', 'js@t.com', 'REG/JDG01')
        course = Course.objects.create(name='Auto Test', code='AT404')
        self.bu = BookedUnit.objects.create(
            lecturer=self.fac, course=course,
            students_course='CS', year_of_study='1', semester='1',
        )
        self.yesterday = (timezone.now() - timezone.timedelta(days=1)).date()

    def _make_lecture(self, lid, total_students):
        return Lecture.objects.create(
            id=lid, lecturer=self.fac, unit_name=self.bu,
            lecture_date=self.yesterday,
            start_time='10:00:00', end_time='12:00:00',
            recurrence_pattern='none', status='scheduled',
            total_students=total_students,
        )

    def test_past_lecture_with_students_becomes_completed(self):
        lec = self._make_lecture('JDG_C01', total_students=1)
        auto_judge_event_statuses()
        lec.refresh_from_db()
        self.assertEqual(lec.status, 'completed')

    def test_past_lecture_with_zero_students_becomes_missed(self):
        lec = self._make_lecture('JDG_M01', total_students=0)
        auto_judge_event_statuses()
        lec.refresh_from_db()
        self.assertEqual(lec.status, 'missed')

    def test_past_personal_event_signed_in_becomes_completed(self):
        past_start = timezone.now() - timezone.timedelta(hours=3)
        past_end   = timezone.now() - timezone.timedelta(hours=2)
        ev = StudentPersonalEvent.objects.create(
            id='JDG_PE_C', student=self.stu, title='Study',
            start_date=past_start, end_date=past_end,
            is_signed_in=True, status='pending',
        )
        auto_judge_event_statuses()
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'completed')

    def test_past_personal_event_not_signed_in_becomes_missed(self):
        past_start = timezone.now() - timezone.timedelta(hours=5)
        past_end   = timezone.now() - timezone.timedelta(hours=4)
        ev = StudentPersonalEvent.objects.create(
            id='JDG_PE_M', student=self.stu, title='Meeting',
            start_date=past_start, end_date=past_end,
            is_signed_in=False, status='pending',
        )
        auto_judge_event_statuses()
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'missed')


# ---------------------------------------------------------------------------
# 5. RBAC – role-based access control
# ---------------------------------------------------------------------------

class RBACPermissionTests(TestCase):
    """Verify that protected views reject users of the wrong role."""

    def setUp(self):
        # Admin – needs is_staff/superuser AND a Faculty record with position='Admin'
        self.u_admin, self.fac_admin = make_faculty('rbac_admin', 'rbac_admin@t.com', position='Admin')
        self.u_admin.is_staff = True
        self.u_admin.is_superuser = True
        self.u_admin.save(update_fields=['is_staff', 'is_superuser'])

        # Lecturer
        self.u_lec, _ = make_faculty('rbac_lec', 'rbac_lec@t.com')

        # Student
        self.u_stu, _ = make_student('rbac_stu', 'rbac_stu@t.com', 'REG/RBAC01')

    # --- anonymous access ---

    def test_anonymous_cannot_access_student_homepage(self):
        resp = self.client.get('/campus/homepage/')
        self.assertNotEqual(resp.status_code, 200)   # redirect to login

    def test_anonymous_cannot_access_admin_dashboard(self):
        resp = self.client.get('/campus/admin-dashboard/')
        self.assertNotEqual(resp.status_code, 200)

    def test_anonymous_cannot_access_faculty_dashboard(self):
        resp = self.client.get('/campus/dashboard/')
        self.assertNotEqual(resp.status_code, 200)

    # --- student cannot reach admin / faculty routes ---

    def test_student_blocked_from_admin_dashboard(self):
        self.client.login(email='rbac_stu@t.com', password='password123')
        resp = self.client.get('/campus/admin-dashboard/')
        # Should redirect or return 403 – NOT 200
        self.assertNotEqual(resp.status_code, 200)

    def test_student_blocked_from_faculty_dashboard(self):
        self.client.login(email='rbac_stu@t.com', password='password123')
        resp = self.client.get('/campus/dashboard/')
        self.assertNotEqual(resp.status_code, 200)

    # --- lecturer cannot reach admin routes ---

    def test_lecturer_blocked_from_admin_dashboard(self):
        self.client.login(email='rbac_lec@t.com', password='password123')
        resp = self.client.get('/campus/admin-dashboard/')
        self.assertNotEqual(resp.status_code, 200)

    # --- correct role gets access ---

    def test_student_can_access_student_homepage(self):
        self.client.login(email='rbac_stu@t.com', password='password123')
        resp = self.client.get('/campus/homepage/')
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_access_admin_dashboard(self):
        self.client.login(email='rbac_admin@t.com', password='password123')
        resp = self.client.get('/campus/admin-dashboard/')
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# 6. View tests – personal report & admin course list
# ---------------------------------------------------------------------------

class PersonalReportTests(TestCase):

    def setUp(self):
        self.u_stu, self.stu = make_student('rep_stu', 'rep_stu@t.com', 'REG/REP01')
        now = timezone.now()
        StudentPersonalEvent.objects.create(
            id='REP_EV1', student=self.stu, title='CompletedEvent',
            start_date=now + timezone.timedelta(hours=1),
            end_date=now   + timezone.timedelta(hours=2),
            status='completed', is_signed_in=True,
        )
        StudentPersonalEvent.objects.create(
            id='REP_EV2', student=self.stu, title='MissedEvent',
            start_date=now + timezone.timedelta(hours=3),
            end_date=now   + timezone.timedelta(hours=4),
            status='missed', is_signed_in=False,
        )

    def test_personal_report_returns_200(self):
        """Personal report view returns HTTP 200 for logged-in student."""
        self.client.login(email='rep_stu@t.com', password='password123')
        resp = self.client.get('/campus/personal-report/')
        self.assertEqual(resp.status_code, 200)

    def test_personal_report_context_contains_stats(self):
        """Report view injects personal_stats into the template context."""
        self.client.login(email='rep_stu@t.com', password='password123')
        resp = self.client.get('/campus/personal-report/')
        self.assertIn('personal_stats', resp.context)
        stats = resp.context['personal_stats']
        self.assertEqual(stats['completed'], 1)
        self.assertEqual(stats['missed'],    1)


class AdminCourseViewTests(TestCase):

    def setUp(self):
        self.u_admin, _ = make_faculty('adm_cv', 'adm_cv@t.com', position='Admin')
        self.u_admin.is_staff = True
        self.u_admin.is_superuser = True
        self.u_admin.save(update_fields=['is_staff', 'is_superuser'])

        _, fac2 = make_faculty('lec_cv', 'lec_cv@t.com')
        course = Course.objects.create(name='Reporting 101', code='REP101')
        self.bu = BookedUnit.objects.create(
            lecturer=fac2, course=course,
            students_course='CS', year_of_study='1', semester='1',
        )

    def test_admin_can_view_all_courses(self):
        self.client.login(email='adm_cv@t.com', password='password123')
        resp = self.client.get('/campus/admin-dashboard/all-courses/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Reporting 101')

    def test_admin_can_view_unit_students(self):
        self.client.login(email='adm_cv@t.com', password='password123')
        resp = self.client.get(f'/campus/unit/{self.bu.id}/students/')
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# 7. Bidirectional calendar API
# ---------------------------------------------------------------------------

class BidirectionalCalendarAPITests(TestCase):
    """get_personal_events returns JSON and only shows the requesting user's events."""

    def setUp(self):
        self.u_stu, self.stu = make_student('cal_stu', 'cal_stu@t.com', 'REG/CAL01')
        _, self.stu2 = make_student('cal_stu2', 'cal_stu2@t.com', 'REG/CAL02')

        now = timezone.now()
        self.ev = StudentPersonalEvent.objects.create(
            id='CAL_EV1', student=self.stu, title='My Event',
            start_date=now + timezone.timedelta(hours=1),
            end_date=now   + timezone.timedelta(hours=2),
        )
        StudentPersonalEvent.objects.create(
            id='CAL_EV2', student=self.stu2, title='Other Event',
            start_date=now + timezone.timedelta(hours=1),
            end_date=now   + timezone.timedelta(hours=2),
        )

    def test_get_personal_events_returns_json(self):
        self.client.login(email='cal_stu@t.com', password='password123')
        resp = self.client.get('/campus/calendar/events/get/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/json')

    def test_get_personal_events_only_own_events(self):
        self.client.login(email='cal_stu@t.com', password='password123')
        resp = self.client.get('/campus/calendar/events/get/')
        import json
        data = json.loads(resp.content)
        titles = [e.get('title', '') for e in data]
        self.assertIn('My Event', titles)
        self.assertNotIn('Other Event', titles)

    def test_unauthenticated_events_api_redirects(self):
        resp = self.client.get('/campus/calendar/events/get/')
        self.assertNotEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# 8. Notification model
# ---------------------------------------------------------------------------

class NotificationModelTests(TestCase):
    """Notification requires a GenericForeignKey target; we use Course as the target object."""

    def setUp(self):
        self.user   = make_user('notif_user', 'notif@t.com')
        self.course = Course.objects.create(name='Notification Course', code='NC001')
        self.ct     = ContentType.objects.get_for_model(Course)

    def _make_notification(self, msg):
        return Notification.objects.create(
            recipient=self.user,
            message=msg,
            content_type=self.ct,
            object_id=self.course.id,
        )

    def test_notification_created_and_unread_by_default(self):
        """New notification is unread by default."""
        n = self._make_notification('You have a new meeting request.')
        self.assertFalse(n.is_read)
        self.assertEqual(str(n), 'You have a new meeting request.')

    def test_mark_notification_as_read(self):
        """Notification can be marked as read."""
        n = self._make_notification('Lecture updated.')
        n.is_read = True
        n.save()
        self.assertTrue(Notification.objects.get(id=n.id).is_read)

    def test_mark_all_read_via_view(self):
        """POST to mark-all-read endpoint clears all unread notifications for user."""
        self._make_notification('N1')
        self._make_notification('N2')
        self.client.login(email='notif@t.com', password='password123')
        resp = self.client.post('/campus/notifications/mark-all-read/')
        self.assertIn(resp.status_code, [200, 302])
        self.assertEqual(
            Notification.objects.filter(recipient=self.user, is_read=False).count(), 0
        )
