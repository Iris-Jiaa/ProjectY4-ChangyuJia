from django.test import TestCase
from .models import User, Student
import uuid

class AccountsModelTests(TestCase):
    def setUp(self):
        # 创建一个基础用户，包含必填的 dob 和 gender
        self.user = User.objects.create_user(
            username='teststudent',
            email='student@test.com',
            password='password123',
            first_name='Test',
            last_name='Student',
            mobile_no='+12125550123',
            dob='2000-01-01',
            gender='Male'
        )

    def test_user_creation(self):
        """测试用户是否能正确创建并保存提醒偏好"""
        self.assertEqual(self.user.email, 'student@test.com')
        self.assertEqual(self.user.reminder_preference, '15min')
        
        # 测试更新偏好
        self.user.reminder_preference = '30min,60min'
        self.user.notification_method = 'email'
        self.user.save()
        
        updated_user = User.objects.get(email='student@test.com')
        self.assertEqual(updated_user.notification_method, 'email')

    def test_student_profile_creation(self):
        """测试学生档案的关联创建"""
        student = Student.objects.create(
            student_name=self.user,
            reg_no='STU/001/2023',
            school='Computing',
            department='IT',
            year='2023',
            semester='1',
            programme='BSc IT',
            course='Computer Science'
        )
        self.assertEqual(student.student_name.username, 'teststudent')
        self.assertEqual(str(student), 'teststudent')
