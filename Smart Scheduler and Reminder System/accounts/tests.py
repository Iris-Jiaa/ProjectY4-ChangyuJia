"""
accounts/tests.py
Unit tests for the accounts module:
  - User model creation and field defaults
  - Reminder preference updates
  - Role properties (is_faculty, is_admin)
  - Student and Faculty profile linking
"""

from django.test import TestCase
from .models import User, Student, Faculty


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------

def make_user(username, email, **kwargs):
    defaults = dict(
        password='password123',
        first_name='Test',
        last_name='User',
        mobile_no='+12125550100',
        dob='2000-01-01',
        gender='Male',
    )
    defaults.update(kwargs)
    return User.objects.create_user(username=username, email=email, **defaults)


# ---------------------------------------------------------------------------
# 1. User model basics
# ---------------------------------------------------------------------------

class UserModelTests(TestCase):

    def setUp(self):
        self.user = make_user('teststudent', 'student@test.com')

    def test_user_created_with_correct_email(self):
        """User email is stored and retrievable."""
        self.assertEqual(self.user.email, 'student@test.com')

    def test_default_reminder_preference(self):
        """Newly created user defaults to 15-minute reminder."""
        self.assertEqual(self.user.reminder_preference, '15min')

    def test_default_notification_method(self):
        """Newly created user defaults to in-app notifications."""
        self.assertEqual(self.user.notification_method, 'in_app')

    def test_update_reminder_preference(self):
        """Reminder preference and notification method can be updated."""
        self.user.reminder_preference = '30min,60min'
        self.user.notification_method = 'email'
        self.user.save()

        refreshed = User.objects.get(email='student@test.com')
        self.assertEqual(refreshed.reminder_preference, '30min,60min')
        self.assertEqual(refreshed.notification_method, 'email')

    def test_str_returns_username(self):
        """__str__ should return the username."""
        self.assertEqual(str(self.user), 'teststudent')

    def test_is_faculty_false_for_plain_user(self):
        """A plain user without a Faculty record is not faculty."""
        self.assertFalse(self.user.is_faculty)

    def test_is_admin_false_for_plain_user(self):
        """A plain user without staff/superuser flag is not admin."""
        self.assertFalse(self.user.is_admin)


# ---------------------------------------------------------------------------
# 2. Student profile
# ---------------------------------------------------------------------------

class StudentProfileTests(TestCase):

    def setUp(self):
        self.user = make_user('student_profile', 'sp@test.com')
        self.student = Student.objects.create(
            student_name=self.user,
            reg_no='STU/001/2024',
            school='Computing',
            department='IT',
            year='2024',
            semester='1',
            programme='BSc IT',
            course='Computer Science',
        )

    def test_student_linked_to_user(self):
        """Student profile username matches the linked user."""
        self.assertEqual(self.student.student_name.username, 'student_profile')

    def test_student_str(self):
        """Student __str__ delegates to username."""
        self.assertEqual(str(self.student), 'student_profile')

    def test_is_student_user_property(self):
        """is_student_user property is True when a Student record exists."""
        self.assertTrue(self.user.is_student_user)


# ---------------------------------------------------------------------------
# 3. Faculty profile and role properties
# ---------------------------------------------------------------------------

class FacultyProfileTests(TestCase):

    def setUp(self):
        self.user = make_user('lecturerA', 'lec@test.com')
        self.faculty = Faculty.objects.create(
            staff=self.user,
            school='SCI',
            department='CS',
            position='Lecturer',
        )

    def test_faculty_linked_to_user(self):
        """Faculty profile is correctly linked via OneToOne."""
        self.assertEqual(self.faculty.staff.username, 'lecturerA')

    def test_faculty_str(self):
        """Faculty __str__ delegates to username."""
        self.assertEqual(str(self.faculty), 'lecturerA')

    def test_is_faculty_property_true(self):
        """is_faculty returns True once a Faculty record exists."""
        self.assertTrue(self.user.is_faculty)

    def test_is_admin_false_for_lecturer(self):
        """A Lecturer position is not considered admin."""
        self.assertFalse(self.user.is_admin)


class AdminRoleTests(TestCase):

    def test_is_admin_true_for_superuser(self):
        """Superuser flag makes is_admin True."""
        admin = make_user('superadmin', 'sa@test.com', is_superuser=True, is_staff=True)
        self.assertTrue(admin.is_admin)

    def test_is_admin_true_for_faculty_admin_position(self):
        """Faculty member with position='Admin' should be admin."""
        user = make_user('fac_admin', 'fa@test.com')
        Faculty.objects.create(staff=user, school='SCI', department='CS', position='Admin')
        self.assertTrue(user.is_admin)
