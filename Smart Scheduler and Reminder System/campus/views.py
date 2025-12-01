from .forms import EditScheduledLectureForm, FeedbackForm, LecturerUnitsBookingForm, StudentsAttendanceConfirmationForm, StudentPersonalEventForm, MeetingRequestForm, ScheduleLectureForm, EditMeetingRequestForm
from accounts.models import Student, Faculty
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Avg, Q
from django.views import View
from .models import BookedUnit, Feedback, Lecture, LectureHall, RegisteredUnit, StudentPersonalEvent, MeetingRequest, FacultyPersonalEvent, Notification
from django.contrib.contenttypes.models import ContentType
from datetime import time, datetime as dt, timedelta
import json
from django.utils import timezone # Added for IntegrityError fix

# students views
@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is True), name='get')
class StudentHomepageView(View):
    form_class = StudentsAttendanceConfirmationForm
    template_name = 'dashboard/students/homepage.html'

    def get(self, request, *args, **kwargs):
        current_date = dt.now().strftime("%Y-%m-%d")
        total_units = RegisteredUnit.objects.filter(student=request.user.student).count()
        total_lectures = Lecture.objects.filter(
            lecturer__department=request.user.student.department,
            unit_name__students_course=request.user.student.course,
            unit_name__year_of_study=request.user.student.year,
            unit_name__semester=request.user.student.semester,
            lecture_date=current_date,
        ).count()
        
        scheduled_lectures_QS = Lecture.objects.filter(
            lecturer__department=request.user.student.department,
            unit_name__students_course=request.user.student.course,
            unit_name__year_of_study=request.user.student.year,
            unit_name__semester=request.user.student.semester,
            lecture_date__lte=current_date,
        ).order_by('-lecture_date', 'start_time', 'unit_name')

        # Debug print statements
        print("--- Debugging scheduled_lectures_QS ---")
        for lec in scheduled_lectures_QS:
            print(f"Lecture ID: '{lec.id}', is_attending: {lec.is_attending}")
        print("--- End Debugging ---")


        # check for lectures before current date
        past_lectures_qs = Lecture.objects.filter(is_taught=False, lecture_date__lte=current_date)
        for _lecture in past_lectures_qs:   # iterate through all lectures in the queryset
            get_lecture = Lecture.objects.get(id=_lecture.id)   # get each lecture in the qs using their id
            if get_lecture.is_taught is False:
                get_lecture.is_taught = True    # if the lecture's "is_taught" is False change it to True.
                get_lecture.save()

        # Scheduled lectures
        events = Lecture.objects.filter(
            lecturer__department=request.user.student.department,
            unit_name__students_course=request.user.student.course,
        )
        event_data = []
        for event in events:
            event_data.append({
                'title': str(event.unit_name),
                'start': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.start_time.strftime('%H:%M:%S'),
                'end': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.end_time.strftime('%H:%M:%S'),
                'backgroundColor': '#f56954', # red
                'borderColor': '#f56954' # red
            })
        
        # Personal events
        personal_events = StudentPersonalEvent.objects.filter(student=request.user.student)
        for event in personal_events:
            event_data.append({
                'title': event.title,
                'start': event.start_date.strftime('%Y-%m-%dT%H:%M:%S'),
                'end': event.end_date.strftime('%Y-%m-%dT%H:%M:%S'),
                'backgroundColor': '#00a65a', # green
                'borderColor': '#00a65a' # green
            })
        
        modified_requests = MeetingRequest.objects.filter(student=request.user.student, status='modified')

        context = {
            'TotalUnits': total_units,
            'TotalLectures': total_lectures,
            'scheduled_lectures': scheduled_lectures_QS,
            'events': json.dumps(event_data),
            'personal_event_form': StudentPersonalEventForm(),
            'modified_requests': modified_requests
        }
        return render(request, self.template_name, context)


@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is True), name='get')
class LecturerCalendarView(View):
    template_name = 'dashboard/students/lecturer_calendar.html'

    def get(self, request, lecturer_id, *args, **kwargs):
        try:
            lecturer = Faculty.objects.get(id=lecturer_id)
            lectures = Lecture.objects.filter(lecturer=lecturer)
            personal_events = FacultyPersonalEvent.objects.filter(faculty=lecturer)
            
            event_data = []
            for event in lectures:
                event_data.append({
                    'title': str(event.unit_name),
                    'start': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.start_time.strftime('%H:%M:%S'),
                    'end': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.end_time.strftime('%H:%M:%S'),
                    'backgroundColor': '#f56954', # red
                    'borderColor': '#f56954' 
                })

            for event in personal_events:
                event_data.append({
                    'title': event.title,
                    'start': event.start_date.isoformat(),
                    'end': event.end_date.isoformat(),
                    'backgroundColor': '#00a65a', # green
                    'borderColor': '#00a65a'
                })

            context = {
                'lecturer': lecturer,
                'events': json.dumps(event_data),
                'meeting_form': MeetingRequestForm(student=request.user.student)
            }
            return render(request, self.template_name, context)
        except Faculty.DoesNotExist:
            messages.error(request, "Lecturer not found.")
            return redirect('student_homepage')


@login_required(login_url='login')
def get_personal_events(request):
    if request.user.is_student:
        events = StudentPersonalEvent.objects.filter(student=request.user.student)
        event_data = []
        for event in events:
            event_data.append({
                'id': event.id,
                'title': event.title,
                'start': event.start_date.isoformat(),
                'end': event.end_date.isoformat(),
                'description': event.description,
                'backgroundColor': '#00a65a', # green
                'borderColor': '#00a65a' # green
            })
        return JsonResponse(event_data, safe=False)
    return JsonResponse([], safe=False)

@login_required(login_url='login')
def add_personal_event(request):
    if request.method == 'POST' and request.user.is_student:
        form = StudentPersonalEventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.student = request.user.student
            event.save()
            return JsonResponse({'status': 'success', 'event_id': event.id})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required(login_url='login')
def update_personal_event(request, event_id):
    if request.method == 'POST' and request.user.is_student:
        try:
            event = StudentPersonalEvent.objects.get(id=event_id, student=request.user.student)
            form = StudentPersonalEventForm(request.POST, instance=event)
            if form.is_valid():
                form.save()
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error', 'errors': form.errors})
        except StudentPersonalEvent.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Event not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required(login_url='login')
def delete_personal_event(request, event_id):
    if request.method == 'POST' and request.user.is_student:
        try:
            event = StudentPersonalEvent.objects.get(id=event_id, student=request.user.student)
            event.delete()
            return JsonResponse({'status': 'success'})
        except StudentPersonalEvent.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Event not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@login_required(login_url='login')
def request_meeting(request, lecturer_id):
    if request.method == 'POST':
        form = MeetingRequestForm(request.POST, student=request.user.student)
        if form.is_valid():
            try:
                lecturer = Faculty.objects.get(id=lecturer_id)
                meeting_request = form.save(commit=False)
                meeting_request.student = request.user.student
                meeting_request.lecturer = lecturer
                meeting_request.save()
                return JsonResponse({'status': 'success', 'message': 'Meeting request submitted successfully.'})
            except Faculty.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Lecturer not found.'})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})


@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is True), name='get')
class StudentsUnitsRegistrationView(View):
    template_name = 'dashboard/students/register-units.html'

    def get(self, request, student_id, *args, **kwargs):
        units_QS = BookedUnit.objects.filter(
            lecturer__department=request.user.student.department,
            students_course=request.user.student.course,
            year_of_study=request.user.student.year,
            semester=request.user.student.semester,
        )
        reg_units_QS = RegisteredUnit.objects.filter(student=request.user.student)

        context = {
            'booked_units': units_QS,
            'registered_units': reg_units_QS,
        }
        return render(request, self.template_name, context)

    def post(self, request, student_id, *args, **kwargs):
        get_unit_field = request.POST.get('register-unit')

        unit_obj = BookedUnit.objects.get(id=get_unit_field)
        try:
            get_reg_unit = RegisteredUnit.objects.filter(unit=unit_obj).exists()
            if get_reg_unit is True:
                messages.warning(request, 'Selected unit already registered!')
                return redirect('unit_registration', student_id)
            
            else:
                register_unit = RegisteredUnit.objects.get_or_create(    
                    unit=unit_obj,
                    student=request.user.student,
                    is_registered=True,
                )

                messages.success(request, 'Unit successfully registered!')
                return redirect('unit_registration', student_id)
        except RegisteredUnit.DoesNotExist:
            messages.error(request, 'Unknown error occured! Contact system administrator')
            return redirect('unit_registration', student_id)

@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is True), name='get')
class LectureAttendanceConfirmationView(View):
    form_class = StudentsAttendanceConfirmationForm
    template_name = 'dashboard/students/confirm-attendance.html'
    current_date = dt.now().strftime('%Y-%m-%d')

    def get(self, request, lecture_id, _student, *args, **kwargs):
        current_date = dt.now().strftime('%Y-%m-%d')
        lec_obj = Lecture.objects.get(id=lecture_id)
        form = self.form_class(instance=lec_obj)
        scheduled_lectures_QS = Lecture.objects.filter(
            lecturer__department=request.user.student.department,
            unit_name__students_course=request.user.student.course,
            unit_name__year_of_study=request.user.student.year,
            unit_name__semester=request.user.student.semester,
            lecture_date=current_date,
            student=None,
        ).order_by('-lecture_date', 'start_time', 'unit_name')


        context = {
            'AttendanceConfirmationForm': form,
            'scheduled_lectures': scheduled_lectures_QS,
            'lec_obj': lec_obj,

        }
        return render(request, self.template_name, context)

    def post(self, request, lecture_id, _student, *args, **kwargs):
        scheduled_lectures_QS = Lecture.objects.filter(
            lecturer__department=request.user.student.department,
            unit_name__students_course=request.user.student.course,
            student=None,
        ).order_by('-lecture_date', '-start_time', 'unit_name')
        
        lec_obj = Lecture.objects.get(id=lecture_id)        
        form = self.form_class(request.POST, instance=lec_obj)
        
        if form.is_valid():
            confirmation = form.save(commit=False)
            confirmation.student = request.user.student
            confirmation.total_students += 1
            confirmation.save()

            # check for lectures before current date
            past_lectures_qs = Lecture.objects.filter(is_taught=False, lecture_date__lte=self.current_date)

            for _lecture in past_lectures_qs:   # iterate through all lectures in the queryset
                get_lecture = Lecture.objects.get(id=_lecture.id)   # get each lecture in the qs using their id

                if get_lecture.is_taught is False:
                    get_lecture.is_taught = True    # if the lecture's "is_taught" is False change it to True.
                    get_lecture.save()

            messages.success(request, 'Confirmation submitted succesfully!')
            return redirect('student_homepage')

        context = {
            'AttendanceConfirmationForm': form,
            'scheduled_lectures': scheduled_lectures_QS,
            'lec_obj': lec_obj,
        
        }
        return render(request, self.template_name, context)
    
@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is True), name='get')
class StudentsLecturesDetailView(View):
    template_name = 'dashboard/students/lectures.html'
    def get(self, request, _student, *args, **kwargs):
        lectures_QS = Lecture.objects.filter(
            lecturer__department=request.user.student.department, unit_name__students_course=request.user.student.course,
            is_taught=True,
        ).order_by('-lecture_date', '-start_time', 'unit_name')

        context = {'scheduled_lectures': lectures_QS}
        return render(request, self.template_name, context)

@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is True), name='get')
class SubmitFeedbackView(View):
    form_class = FeedbackForm
    template_name = 'dashboard/students/feedback.html'

    def get(self, request, hall_id, *args, **kwargs):
        lecture_hall = LectureHall.objects.get(id=hall_id)
        form = self.form_class()

        context = {'FeedbackForm': form, 'lecture_hall_obj': lecture_hall}
        return render(request, self.template_name, context)
    
    def post(self, request, hall_id, *args, **kwargs):
        lecture_hall = LectureHall.objects.get(id=hall_id)
        form = self.form_class(request.POST)

        if form.is_valid():
            new_feedback = form.save(commit=False)
            new_feedback.student = request.user.student
            new_feedback.lecture_hall = lecture_hall
            new_feedback.save()

            # calculate the average rating of the lecture hall/room based on all rate scores in submitted user feedback
            avg_rating = Feedback.objects.aggregate(avg_rating=Avg('rate_score'))['avg_rating']
            lecture_hall.rating = avg_rating
            lecture_hall.save()

            messages.info(request, 'Thank you for your feedback!')
            return redirect('student_feedback', hall_id)

        context = {'FeedbackForm': form}
        return render(request, self.template_name, context)

# faculty views
@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='get')
class FacultyDashboardView(View):
    template_name = 'dashboard/faculty/homepage.html'

    def get(self, request, *args, **kwargs):
        current_date = dt.now().strftime('%Y-%m-%d')
        total_booked_units = BookedUnit.objects.filter(lecturer=request.user.faculty).count()
        scheduled_lectures_QS = Lecture.objects.filter(lecturer=request.user.faculty, lecture_date=current_date).order_by('lecture_date', 'start_time')
        pending_requests_count = MeetingRequest.objects.filter(lecturer=request.user.faculty, status='pending').count()

        # check for lectures before current date
        past_lectures_qs = Lecture.objects.filter(is_taught=False, lecture_date__lte=current_date)
        for _lecture in past_lectures_qs:   # iterate through all lectures in the queryset
            get_lecture = Lecture.objects.get(id=_lecture.id)   # get each lecture in the qs using their id
            if get_lecture.is_taught is False:
                get_lecture.is_taught = True    # if the lecture's "is_taught" is False change it to True.
                get_lecture.save()
        
        # Get all lectures for the calendar view
        all_lectures = Lecture.objects.filter(lecturer=request.user.faculty)
        personal_events = FacultyPersonalEvent.objects.filter(faculty=request.user.faculty)

        event_data = []
        for event in all_lectures:
            event_data.append({
                'title': str(event.unit_name),
                'start': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.start_time.strftime('%H:%M:%S'),
                'end': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.end_time.strftime('%H:%M:%S'),
                'backgroundColor': '#f56954', # red
                'borderColor': '#f56954',
                'lecturer_id': event.lecturer.id, # Debugging: Add lecturer ID
                'lecturer_name': str(event.lecturer) # Debugging: Add lecturer name
            })

        for event in personal_events:
            event_data.append({
                'title': event.title,
                'start': event.start_date.isoformat(),
                'end': event.end_date.isoformat(),
                'backgroundColor': '#00a65a', # green
                'borderColor': '#00a65a'
            })

        context = {
            'TotalBookedUnits': total_booked_units,
            'scheduled_lectures': scheduled_lectures_QS,
            'events': json.dumps(event_data),
            'pending_requests_count': pending_requests_count,
        }
        return render(request, self.template_name, context)

@login_required(login_url='login')
def approve_meeting_request(request, request_id):
    try:
        meeting_request = MeetingRequest.objects.get(id=request_id)
        if request.user.faculty == meeting_request.lecturer:
            meeting_request.status = 'approved'
            meeting_request.save()

            # Create a personal event for the student
            StudentPersonalEvent.objects.create(
                student=meeting_request.student,
                title=f"Meeting with {meeting_request.lecturer.staff.first_name} {meeting_request.lecturer.staff.last_name}",
                description=meeting_request.description,
                start_date=meeting_request.start_time,
                end_date=meeting_request.end_time,
            )

            # Create a personal event for the faculty
            FacultyPersonalEvent.objects.create(
                faculty=meeting_request.lecturer,
                title=f"Meeting with {meeting_request.student.student_name}",
                description=meeting_request.description,
                start_date=meeting_request.start_time,
                end_date=meeting_request.end_time,
            )

            # Create a notification for the student
            Notification.objects.create(
                recipient=meeting_request.student.student_name,
                message=f"Your meeting request with {meeting_request.lecturer.staff.first_name} {meeting_request.lecturer.staff.last_name} has been approved.",
                content_object=meeting_request
            )

            messages.success(request, 'Meeting request approved.')
        else:
            messages.error(request, 'You are not authorized to approve this request.')
    except MeetingRequest.DoesNotExist:
        messages.error(request, 'Meeting request not found.')
    return redirect('manage_meeting_requests')

@login_required(login_url='login')
def reject_meeting_request(request, request_id):
    try:
        meeting_request = MeetingRequest.objects.get(id=request_id)
        if request.user.faculty == meeting_request.lecturer:
            meeting_request.status = 'rejected'
            meeting_request.save()
            messages.success(request, 'Meeting request rejected.')
        else:
            messages.error(request, 'You are not authorized to reject this request.')
    except MeetingRequest.DoesNotExist:
        messages.error(request, 'Meeting request not found.')
    return redirect('manage_meeting_requests')


@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='get')
class ManageMeetingRequestsView(View):
    template_name = 'dashboard/faculty/manage_requests.html'

    def get(self, request, *args, **kwargs):
        pending_requests = MeetingRequest.objects.filter(lecturer=request.user.faculty, status='pending').order_by('start_time')
        context = {
            'requests': pending_requests
        }
        return render(request, self.template_name, context)


@method_decorator(login_required(login_url='login'), name='dispatch')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='dispatch')
class ScheduleLectureView(View):
    template_name = 'dashboard/faculty/schedule-lecture.html'
    form_class = ScheduleLectureForm

    def get(self, request, staff_id, staff_name, *args, **kwargs):
        booked_units_QS = BookedUnit.objects.filter(lecturer__id=staff_id).exclude(id='')
        
        forms_by_unit = {}
        for unit in booked_units_QS:
            forms_by_unit[unit.id] = self.form_class(lecturer=request.user.faculty)

        context = {
            'booked_units': booked_units_QS,
            'forms_by_unit': forms_by_unit,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, staff_id, staff_name, unit_id, *args, **kwargs):
        try:
            unit_instance = BookedUnit.objects.get(id=unit_id)
        except BookedUnit.DoesNotExist:
            messages.error(request, "The unit you tried to schedule for does not exist.")
            return redirect('schedule_lecture_list', staff_id=staff_id, staff_name=staff_name)

        form = self.form_class(request.POST, lecturer=request.user.faculty)

        if form.is_valid():
            new_scheduled_lecture = form.save(commit=False)
            new_scheduled_lecture.lecturer = request.user.faculty
            new_scheduled_lecture.unit_name = unit_instance
            new_scheduled_lecture.date_scheduled = timezone.now() # Explicitly set date_scheduled
            new_scheduled_lecture.save()

            messages.success(request, 'Lecture successfully scheduled!')
            return redirect('faculty_homepage')
        else:
            messages.warning(request, 'The form has errors. Please correct them and try again.')
            
            booked_units_QS = BookedUnit.objects.filter(lecturer=staff_id)
            forms_by_unit = {}
            for unit in booked_units_QS:
                if str(unit.id) == unit_id:
                    forms_by_unit[unit.id] = form
                else:
                    forms_by_unit[unit.id] = self.form_class(lecturer=request.user.faculty)

            context = {
                'booked_units': booked_units_QS,
                'forms_by_unit': forms_by_unit,
            }
            return render(request, self.template_name, context)

@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='get')
class AssignUnitsforLecturersView(View):
    form_class = LecturerUnitsBookingForm
    template_name = 'dashboard/faculty/book-units.html'

    def get(self, request, staff_id, *args, **kwargs):
        booked_units_QS = BookedUnit.objects.filter(lecturer__department=request.user.faculty.department)
        form = self.form_class()

        context = {
            'LecturersUnitsBookingForm': form,
            'booked_units': booked_units_QS
        }
        return render(request, self.template_name, context)
    
    def post(self, request, staff_id, *args, **kwargs):
        form = self.form_class(request.POST)

        if form.is_valid():
            booked_unit_instance = form.save(commit=False)
            booked_unit_instance.booking_date = timezone.now() # Explicitly set booking_date
            booked_unit_instance.save()
            
            messages.info(request, 'Unit assigned to lecturer successfully!')
            return redirect('assign_units', staff_id)

        context = {'LecturersUnitsBookingForm': form}
        return render(request, self.template_name, context)

@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='get')
class LecturesDetailView(View):
    template_name = 'dashboard/faculty/lectures.html'

    def get(self, request, staff_name, staff_id, *args, **kwargs):
        scheduled_lectures_QS = Lecture.objects.filter(lecturer=request.user.faculty, is_taught=True).order_by('unit_name')

        context = {
            'scheduled_lectures': scheduled_lectures_QS,

        }
        return render(request, self.template_name, context)
    
    def post(self, request, staff_name, staff_id, *args, **kwargs):
        lecture_record_ID = request.POST.get('scheduled-lecture')
        scheduled_lectures_QS = Lecture.objects.get(id=lecture_record_ID)
        scheduled_lectures_QS.delete()

        messages.error(request, 'You deleted a scheduled lecture!')
        return redirect('lectures_records', staff_name, staff_id)


@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='get')
class ViewUnitStudentsView(View):
    template_name = 'dashboard/faculty/unit_students.html'

    def get(self, request, unit_id, *args, **kwargs):
        try:
            unit = BookedUnit.objects.get(id=unit_id)
            # Ensure the lecturer accessing this page is the one assigned to the unit
            if unit.lecturer != request.user.faculty:
                messages.error(request, "You are not authorized to view students for this unit.")
                return redirect('lectures_records', request.user.faculty.id, request.user.faculty)

            registered_students = RegisteredUnit.objects.filter(unit=unit).select_related('student__student_name')
            
            context = {
                'unit': unit,
                'students': registered_students
            }
            return render(request, self.template_name, context)
        except BookedUnit.DoesNotExist:
            messages.error(request, "The selected unit does not exist.")
            return redirect('lectures_records', request.user.faculty.id, request.user.faculty)


@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='get')
class StudentCalendarView(View):
    template_name = 'dashboard/faculty/student_calendar.html'

    def get(self, request, student_id, *args, **kwargs):
        try:
            student = Student.objects.get(id=student_id)
            
            # Security check: Ensure the student is in the same department as the lecturer
            if student.department != request.user.faculty.department:
                messages.error(request, "You are not authorized to view this student's calendar.")
                return redirect('faculty_homepage')

            event_data = []

            # Get student's lectures
            student_lectures = Lecture.objects.filter(
                unit_name__students_course=student.course,
                unit_name__year_of_study=student.year,
                unit_name__semester=student.semester
            )
            for event in student_lectures:
                event_data.append({
                    'title': str(event.unit_name),
                    'start': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.start_time.strftime('%H:%M:%S'),
                    'end': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.end_time.strftime('%H:%M:%S'),
                    'backgroundColor': '#f56954', # red
                    'borderColor': '#f56954'
                })

            # Get student's personal events
            personal_events = StudentPersonalEvent.objects.filter(student=student)
            for event in personal_events:
                event_data.append({
                    'title': event.title,
                    'start': event.start_date.isoformat(),
                    'end': event.end_date.isoformat(),
                    'backgroundColor': '#00a65a', # green
                    'borderColor': '#00a65a'
                })

            context = {
                'student': student,
                'events': json.dumps(event_data)
            }
            return render(request, self.template_name, context)
        except Student.DoesNotExist:
            messages.error(request, "Student not found.")
            return redirect('faculty_homepage')


@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='get')
class EditScheduledLecturesView(View):
    form_class = EditScheduledLectureForm
    template_name = 'dashboard/faculty/edit.html'

    def get(self, request, staff_id, lecture_id, *args, **kwargs):
        lectures_QS = Lecture.objects.get(id=lecture_id)
        form = self.form_class(instance=lectures_QS)

        context = {
            'EditScheduledLectureForm': form,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, staff_id, lecture_id, *args, **kwargs):
        lectures_QS = Lecture.objects.get(id=lecture_id)
        form = self.form_class(request.POST, instance=lectures_QS)

        if form.is_valid():
            form.save()

            messages.warning(request, 'You updated a scheduled lecture!')
            return redirect('lectures_records', staff_id, request.user.faculty)

        context = {
            'EditScheduledLectureForm': form,
        }
        return render(request, self.template_name, context)

@login_required(login_url='login')
def find_available_slots(request, lecturer_id):
    if request.method == 'GET':
        try:
            lecturer = Faculty.objects.get(id=lecturer_id)
            student = request.user.student
            duration = int(request.GET.get('duration', 60)) # in minutes
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')

            if not start_date_str or not end_date_str:
                return JsonResponse({'status': 'error', 'message': 'Please provide a start and end date.'})

            start_date = dt.fromisoformat(start_date_str)
            end_date = dt.fromisoformat(end_date_str)

            # Get all events for the lecturer
            lecturer_events = []
            lectures = Lecture.objects.filter(lecturer=lecturer, lecture_date__range=[start_date.date(), end_date.date()])
            for event in lectures:
                start = dt.combine(event.lecture_date, event.start_time)
                end = dt.combine(event.lecture_date, event.end_time)
                lecturer_events.append((start, end))

            personal_events = FacultyPersonalEvent.objects.filter(faculty=lecturer, start_date__range=[start_date, end_date])
            for event in personal_events:
                lecturer_events.append((event.start_date, event.end_date))

            # Get all events for the student
            student_events = []
            student_lectures = Lecture.objects.filter(
                unit_name__students_course=student.course,
                unit_name__year_of_study=student.year,
                unit_name__semester=student.semester,
                lecture_date__range=[start_date.date(), end_date.date()]
            )
            for event in student_lectures:
                start = dt.combine(event.lecture_date, event.start_time)
                end = dt.combine(event.lecture_date, event.end_time)
                student_events.append((start, end))
            
            student_personal_events = StudentPersonalEvent.objects.filter(student=student, start_date__range=[start_date, end_date])
            for event in student_personal_events:
                student_events.append((event.start_date, event.end_date))

            # Combine and sort all events
            all_events = sorted(lecturer_events + student_events)

            # Find available slots
            available_slots = []
            current_time = start_date
            while current_time < end_date:
                is_free = True
                for event_start, event_end in all_events:
                    if current_time < event_end and current_time + timedelta(minutes=duration) > event_start:
                        is_free = False
                        current_time = event_end
                        break
                
                if is_free:
                    slot_end = current_time + timedelta(minutes=duration)
                    if slot_end <= end_date:
                        available_slots.append({
                            'start': current_time.isoformat(),
                            'end': slot_end.isoformat()
                        })
                    current_time = slot_end
            
            return JsonResponse({'status': 'success', 'available_slots': available_slots})

        except Faculty.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Lecturer not found.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

@method_decorator(login_required(login_url='login'), name='dispatch')
@method_decorator(user_passes_test(lambda u: u.is_faculty), name='dispatch')
class EditMeetingRequestView(View):
    form_class = EditMeetingRequestForm
    template_name = 'dashboard/faculty/edit_meeting_request.html'

    def get(self, request, request_id, *args, **kwargs):
        try:
            meeting_request = MeetingRequest.objects.get(id=request_id, lecturer=request.user.faculty)
            form = self.form_class(instance=meeting_request)
            context = {
                'form': form,
                'request_obj': meeting_request
            }
            return render(request, self.template_name, context)
        except MeetingRequest.DoesNotExist:
            messages.error(request, 'Meeting request not found.')
            return redirect('manage_meeting_requests')

    def post(self, request, request_id, *args, **kwargs):
        try:
            meeting_request = MeetingRequest.objects.get(id=request_id, lecturer=request.user.faculty)
            form = self.form_class(request.POST, instance=meeting_request)
            if form.is_valid():
                modified_request = form.save(commit=False)
                modified_request.status = 'modified'
                modified_request.save()
                messages.success(request, 'Meeting request has been modified and sent to the student for approval.')
                return redirect('manage_meeting_requests')
            
            context = {
                'form': form,
                'request_obj': meeting_request
            }
            return render(request, self.template_name, context)
        except MeetingRequest.DoesNotExist:
            messages.error(request, 'Meeting request not found.')
            return redirect('manage_meeting_requests')

@login_required(login_url='login')
def accept_meeting_request(request, request_id):
    try:
        meeting_request = MeetingRequest.objects.get(id=request_id, student=request.user.student)
        meeting_request.status = 'approved'
        meeting_request.save()
        messages.success(request, 'Meeting request has been accepted.')
    except MeetingRequest.DoesNotExist:
        messages.error(request, 'Meeting request not found.')
    return redirect('student_homepage')

@login_required(login_url='login')
def reject_modified_meeting_request(request, request_id):
    try:
        meeting_request = MeetingRequest.objects.get(id=request_id, student=request.user.student)
        meeting_request.status = 'rejected'
        meeting_request.save()
        messages.success(request, 'Meeting request has been rejected.')
    except MeetingRequest.DoesNotExist:
        messages.error(request, 'Meeting request not found.')
    return redirect('student_homepage')


@login_required(login_url='login')
def view_all_notifications(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-date_created')
    has_unread_notifications = notifications.filter(is_read=False).exists()
    
    if request.user.is_student:
        base_template = 'dashboard/students/base.html'
    else: # Assuming faculty or admin
        base_template = 'dashboard/faculty/base.html'

    return render(request, 'notifications/all_notifications.html', {
        'notifications': notifications,
        'base_template': base_template,
        'has_unread_notifications': has_unread_notifications
    })

@login_required(login_url='login')
def mark_all_notifications_as_read(request):
    if request.method == 'POST':
        try:
            # Mark all unread notifications for the current user as read
            notifications = Notification.objects.filter(recipient=request.user, is_read=False)
            for notification in notifications:
                notification.is_read = True
                notification.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)

@login_required(login_url='login')
def mark_notification_as_read(request, notification_id):
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=notification_id, recipient=request.user)
            notification.is_read = True
            notification.save()
            return JsonResponse({'status': 'success'})
        except Notification.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Notification not found.'}, status=404)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)


@login_required(login_url='login')
def get_unread_notifications(request):
    notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-date_created')
    data = []
    for n in notifications:
        item = {
            'message': n.message,
            'url': n.content_object.get_absolute_url() if n.content_object and hasattr(n.content_object, 'get_absolute_url') else '#',
            'notification_type': n.notification_type, # Include notification type
            'is_event_reminder': False,
            'event_start_time': None,
            'event_title': None,
        }
        
        # Check if the notification is for a Lecture or MeetingRequest
        if n.content_object:
            if isinstance(n.content_object, Lecture):
                item['is_event_reminder'] = True
                item['event_start_time'] = n.content_object.start_time.strftime('%H:%M')
                item['event_title'] = str(n.content_object.unit_name)
            elif isinstance(n.content_object, MeetingRequest):
                item['is_event_reminder'] = True
                item['event_start_time'] = n.content_object.start_time.strftime('%H:%M')
                item['event_title'] = n.content_object.title
        data.append(item)
    return JsonResponse(data, safe=False)


@login_required(login_url='login')
def unread_notifications_api(request):
    unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-date_created')
    notifications_data = [{'id': n.id, 'message': n.message} for n in unread_notifications]
    return JsonResponse({
        'count': unread_notifications.count(),
        'notifications': notifications_data
    })
