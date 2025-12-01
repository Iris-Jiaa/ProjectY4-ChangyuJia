from django.urls import path, re_path
from . import views

urlpatterns = [
    path('homepage/', views.StudentHomepageView.as_view(), name='student_homepage'),
    path('lecturer/<str:lecturer_id>/calendar/', views.LecturerCalendarView.as_view(), name='lecturer_calendar'),
    path('lecturer/<str:lecturer_id>/find-slots/', views.find_available_slots, name='find_available_slots'),
    path('lecturer/<str:lecturer_id>/request-meeting/', views.request_meeting, name='request_meeting'),
    path('calendar/events/add/', views.add_personal_event, name='add_personal_event'),
    path('calendar/events/get/', views.get_personal_events, name='get_personal_events'),
    path('calendar/events/update/<str:event_id>/', views.update_personal_event, name='update_personal_event'),
    path('calendar/events/delete/<str:event_id>/', views.delete_personal_event, name='delete_personal_event'),
    path('units/<str:student_id>/register/', views.StudentsUnitsRegistrationView.as_view(), name='unit_registration'),
    path('lectures/<str:_student>/', views.StudentsLecturesDetailView.as_view(), name='student_lecture_records'),
    path('lecture/<str:lecture_id>/schedule/<str:_student>/confirm/', views.LectureAttendanceConfirmationView.as_view(), name='confirm_attendance'),
    path('halls/<str:hall_id>/feedback/', views.SubmitFeedbackView.as_view(), name='student_feedback'),
    
    path('dashboard/', views.FacultyDashboardView.as_view(), name='faculty_homepage'),
    path('manage-requests/', views.ManageMeetingRequestsView.as_view(), name='manage_meeting_requests'),
    path('approve-request/<str:request_id>/', views.approve_meeting_request, name='approve_meeting_request'),
    path('reject-request/<str:request_id>/', views.reject_meeting_request, name='reject_meeting_request'),
    path('edit-request/<str:request_id>/', views.EditMeetingRequestView.as_view(), name='edit_meeting_request'),
    path('<str:staff_id>/lecture/<str:staff_name>/schedule/', views.ScheduleLectureView.as_view(), name='schedule_lecture_list'),
    path('<str:staff_id>/lecture/<str:staff_name>/schedule/<str:unit_id>/', views.ScheduleLectureView.as_view(), name='schedule_lecture_submit'),
    path('units/<str:staff_id>/book/', views.AssignUnitsforLecturersView.as_view(), name='assign_units'),
    path('records/faculty/<str:staff_id>/<str:staff_name>/', views.LecturesDetailView.as_view(), name='view_faculty_lectures'),
    path('unit/<str:unit_id>/students/', views.ViewUnitStudentsView.as_view(), name='view_unit_students'),
    path('student/<str:student_id>/calendar/', views.StudentCalendarView.as_view(), name='view_student_calendar'),
    path('<str:staff_id>/lecture/<str:lecture_id>/edit/', views.EditScheduledLecturesView.as_view(), name='edit_schedule'),

    path('accept-meeting-request/<str:request_id>/', views.accept_meeting_request, name='accept_meeting_request'),
    path('reject-modified-meeting-request/<str:request_id>/', views.reject_modified_meeting_request, name='reject_modified_meeting_request'),
    path('notifications/all/', views.view_all_notifications, name='view_all_notifications'),
    path('notifications/mark-read/<str:notification_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_as_read, name='mark_all_notifications_as_read'),
    path('notifications/unread/', views.get_unread_notifications, name='get_unread_notifications'),
    path('notifications/api/unread/', views.unread_notifications_api, name='unread_notifications_api'),
]
