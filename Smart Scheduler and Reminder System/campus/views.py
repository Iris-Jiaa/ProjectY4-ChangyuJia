from .forms import EditScheduledLectureForm, FeedbackForm, LecturerUnitsBookingForm, StudentsAttendanceConfirmationForm, StudentPersonalEventForm, FacultyPersonalEventForm, MeetingRequestForm, ScheduleLectureForm, EditMeetingRequestForm
from accounts.models import Student, Faculty
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Avg, Q
from django.views import View
from .models import BookedUnit, Course, EventComment, Feedback, Holiday, Lecture, LectureHall, RegisteredUnit, StudentPersonalEvent, MeetingRequest, FacultyPersonalEvent, Notification
from django.contrib.contenttypes.models import ContentType
from datetime import time, datetime as dt, timedelta
import json
import random
from django.utils import timezone # Added for IntegrityError fix
from .utils import check_student_conflicts, create_recurring_instances # Import the conflict detection and recurrence utility


@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: user.is_admin), name='get')
class AdminDashboardView(View):
    template_name = 'dashboard/admin/homepage.html'

    def get(self, request, *args, **kwargs):
        current_date = dt.now().strftime("%Y-%m-%d")

        scheduled_lectures_QS = Lecture.objects.filter(
            lecture_date=current_date,
        ).select_related(
            'lecturer__staff',
            'unit_name__course',
            'lecture_hall'
        ).order_by('lecture_date', 'start_time', 'unit_name__course__name')

        context = {
            'scheduled_lectures': scheduled_lectures_QS,
        }
        return render(request, self.template_name, context)

# new view for admin to list all students
@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: user.is_admin), name='get')
class AdminAllStudentsView(View):
    template_name = 'dashboard/admin/all_students.html'

    def get(self, request, *args, **kwargs):
        all_students = Student.objects.all().select_related('student_name').exclude(id='').order_by('student_name__last_name', 'student_name__first_name')
        
        context = {
            'all_students': all_students,
        }
        return render(request, self.template_name, context)

# new view for admin to list all courses/units
@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: user.is_admin), name='get')
class AdminAllCoursesView(View):
    template_name = 'dashboard/admin/all_courses.html'

    def get(self, request, *args, **kwargs):
        all_units = BookedUnit.objects.all().select_related('lecturer__staff', 'course').exclude(id='').order_by('course__name')

        context = {
            'all_units': all_units,
        }
        return render(request, self.template_name, context)


@method_decorator(login_required(login_url='login'), name='dispatch')
@method_decorator(user_passes_test(lambda user: user.is_admin), name='dispatch')
class AdminHolidayView(View):
    """Admin view for managing holiday / exam-week periods."""
    template_name = 'dashboard/admin/holidays.html'

    def get(self, request, *args, **kwargs):
        holidays = Holiday.objects.all().order_by('start_date')
        context = {'holidays': holidays}
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        name = request.POST.get('name', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()

        errors = []
        if not name:
            errors.append('Holiday name is required.')
        if not start_date:
            errors.append('Start date is required.')
        if not end_date:
            errors.append('End date is required.')
        if start_date and end_date and start_date > end_date:
            errors.append('End date cannot be earlier than start date.')

        if errors:
            holidays = Holiday.objects.all().order_by('start_date')
            return render(request, self.template_name, {'holidays': holidays, 'errors': errors, 'form_data': request.POST})

        Holiday.objects.create(name=name, start_date=start_date, end_date=end_date)
        messages.success(request, f'Holiday "{name}" has been added successfully.')
        return redirect('admin_holidays')


@login_required(login_url='login')
@user_passes_test(lambda user: user.is_admin)
def delete_holiday(request, holiday_id):
    """Delete a holiday record."""
    if request.method == 'POST':
        try:
            holiday = Holiday.objects.get(id=holiday_id)
            name = holiday.name
            holiday.delete()
            messages.success(request, f'Holiday "{name}" has been deleted.')
        except Holiday.DoesNotExist:
            messages.error(request, 'Holiday not found.')
    return redirect('admin_holidays')


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
            unit_name__registeredunit__student=request.user.student, # Filter by units registered by the student
            lecture_date__gte=current_date, # Show upcoming lectures
        ).select_related(
            'lecturer__staff',
            'unit_name__course',
            'lecture_hall'
        ).order_by('lecture_date', 'start_time', 'unit_name__course__name')

        # Auto-mark missed lectures: if end_time has passed and student hasn't signed in
        now_dt = timezone.now()
        for lecture in scheduled_lectures_QS:
            if lecture.status == 'scheduled' and not lecture.is_attending:
                end_dt = timezone.make_aware(
                    dt.combine(lecture.lecture_date, lecture.end_time)
                )
                if end_dt < now_dt:
                    Lecture.objects.filter(pk=lecture.pk).update(status='missed')
                    absent_msg = f"You were marked absent for '{lecture.unit_name.course.name}' on {lecture.lecture_date.strftime('%d %b %Y')}."
                    if not Notification.objects.filter(recipient=request.user, message=absent_msg).exists():
                        Notification.objects.create(
                            recipient=request.user,
                            message=absent_msg,
                            content_type=ContentType.objects.get_for_model(lecture),
                            object_id=lecture.pk,
                        )
        # Re-fetch after status updates
        scheduled_lectures_QS = scheduled_lectures_QS.all()

        # check for lectures before current date
        past_lectures_qs = Lecture.objects.filter(is_taught=False, lecture_date__lte=current_date)
        for _lecture in past_lectures_qs:   # iterate through all lectures in the queryset
            get_lecture = Lecture.objects.get(id=_lecture.id)   # get each lecture in the qs using their id
            if get_lecture.is_taught is False:
                get_lecture.is_taught = True    # if the lecture's "is_taught" is False change it to True.
                get_lecture.save()

        # Scheduled lectures for the calendar - ONLY LECTURES
        registered_units = RegisteredUnit.objects.filter(student=request.user.student)
        booked_units = [reg_unit.unit for reg_unit in registered_units]
        lecture_events_objs = Lecture.objects.filter(unit_name__in=booked_units)
        
        lecture_events = []
        for event in lecture_events_objs:
            lecture_events.append({
                'id': event.id,
                'title': str(event.unit_name.course.name),
                'start': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.start_time.strftime('%H:%M:%S'),
                'end': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.end_time.strftime('%H:%M:%S'),
                'is_signed_in': event.is_attending,
                'status': event.status,
                'event_type': 'lecture',
                'backgroundColor': '#f56954', # red
                'borderColor': '#f56954' # red
            })

        # Add approved meetings to calendar
        approved_meetings = MeetingRequest.objects.filter(student=request.user.student, status='approved')
        for meeting in approved_meetings:
            lecture_events.append({
                'id': meeting.id,
                'title': meeting.title,
                'start': meeting.start_time.isoformat(),
                'end': meeting.end_time.isoformat(),
                'description': meeting.description,
                'is_signed_in': meeting.is_signed_in,
                'status': meeting.status,
                'event_type': 'meeting',
                'backgroundColor': '#3c8dbc', # blue
                'borderColor': '#3c8dbc'
            })
        
        modified_requests = MeetingRequest.objects.filter(student=request.user.student, status='modified')

        # Detect conflicts
        conflicts = check_student_conflicts(request.user.student)

        # Smart recommendations: courses available for this student's profile not yet registered
        registered_unit_ids = RegisteredUnit.objects.filter(
            student=request.user.student
        ).values_list('unit_id', flat=True)
        recommended_units = BookedUnit.objects.filter(
            students_course=request.user.student.course,
            year_of_study=request.user.student.year,
            semester=request.user.student.semester,
        ).exclude(id__in=registered_unit_ids).select_related('course', 'lecturer__staff')[:5]

        context = {
            'TotalUnits': total_units,
            'TotalLectures': total_lectures,
            'scheduled_lectures': scheduled_lectures_QS,
            'events': json.dumps(lecture_events),
            'personal_event_form': StudentPersonalEventForm(),
            'modified_requests': modified_requests,
            'conflicts': conflicts,
            'recommended_units': recommended_units,
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
                    'title': str(event.unit_name.course.name),
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
    PRIORITY_COLORS = {
        'low':    '#28a745',  # green
        'medium': '#fd7e14',  # orange
        'high':   '#dc3545',  # red
    }
    event_data = []
    now = timezone.now()
    if request.user.is_student:
        events = StudentPersonalEvent.objects.filter(
            student=request.user.student,
            end_date__gte=now,
        )
        for event in events:
            color = PRIORITY_COLORS.get(event.priority, '#fd7e14')
            event_data.append({
                'id': event.id,
                'title': event.title,
                'start': event.start_date.isoformat(),
                'end': event.end_date.isoformat(),
                'description': event.description,
                'is_signed_in': event.is_signed_in,
                'status': event.status,
                'priority': event.priority,
                'backgroundColor': color,
                'borderColor': color,
            })
    elif hasattr(request.user, 'faculty'):
        events = FacultyPersonalEvent.objects.filter(
            faculty=request.user.faculty,
            end_date__gte=now,
        )
        for event in events:
            color = PRIORITY_COLORS.get(event.priority, '#fd7e14')
            event_data.append({
                'id': event.id,
                'title': event.title,
                'start': event.start_date.isoformat(),
                'end': event.end_date.isoformat(),
                'description': event.description,
                'is_signed_in': event.is_signed_in,
                'status': event.status,
                'priority': event.priority,
                'backgroundColor': color,
                'borderColor': color,
            })
    return JsonResponse(event_data, safe=False)


@login_required(login_url='login')
def get_holidays_api(request):
    """Return all holiday/exam-week ranges as FullCalendar-compatible background events."""
    holidays_qs = Holiday.objects.all()
    data = []
    for h in holidays_qs:
        # FullCalendar end is exclusive, so add 1 day to include the end date
        end_exclusive = h.end_date + timedelta(days=1)
        data.append({
            'id': h.id,
            'title': h.name,
            'start': h.start_date.isoformat(),
            'end': end_exclusive.isoformat(),
            'display': 'background',
            'backgroundColor': '#b0b0b0',
            'classNames': ['holiday-bg-event'],
            'extendedProps': {
                'is_holiday': True,
                'holiday_name': h.name,
            }
        })
    return JsonResponse(data, safe=False)


@login_required(login_url='login')
def add_personal_event(request):
    if request.method == 'POST':
        if request.user.is_student:
            form = StudentPersonalEventForm(request.POST, student_instance=request.user.student)
            form.instance.student = request.user.student
            if form.is_valid():
                try:
                    event = form.save()
                    create_recurring_instances(event)
                    return JsonResponse({'status': 'success', 'event_id': event.id})
                except Exception as e:
                    return JsonResponse({'status': 'error', 'message': str(e)})
            else:
                return JsonResponse({'status': 'error', 'errors': form.errors})
        elif hasattr(request.user, 'faculty'):
            form = FacultyPersonalEventForm(request.POST, faculty_instance=request.user.faculty)
            form.instance.faculty = request.user.faculty
            if form.is_valid():
                try:
                    event = form.save()
                    create_recurring_instances(event)
                    return JsonResponse({'status': 'success', 'event_id': event.id})
                except Exception as e:
                    return JsonResponse({'status': 'error', 'message': str(e)})
            else:
                return JsonResponse({'status': 'error', 'errors': form.errors})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required(login_url='login')
def update_personal_event(request, event_id):
    if request.method == 'POST':
        if request.user.is_student:
            try:
                event = StudentPersonalEvent.objects.get(id=event_id, student=request.user.student)
                form = StudentPersonalEventForm(request.POST, instance=event, student_instance=request.user.student)
                if form.is_valid():
                    form.save()
                    return JsonResponse({'status': 'success'})
                else:
                    return JsonResponse({'status': 'error', 'errors': form.errors})
            except StudentPersonalEvent.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Event not found.'})
        elif hasattr(request.user, 'faculty'):
            try:
                event = FacultyPersonalEvent.objects.get(id=event_id, faculty=request.user.faculty)
                form = FacultyPersonalEventForm(request.POST, instance=event, faculty_instance=request.user.faculty)
                if form.is_valid():
                    form.save()
                    return JsonResponse({'status': 'success'})
                else:
                    return JsonResponse({'status': 'error', 'errors': form.errors})
            except FacultyPersonalEvent.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Event not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required(login_url='login')
def delete_personal_event(request, event_id):
    if request.method == 'POST':
        if request.user.is_student:
            try:
                event = StudentPersonalEvent.objects.get(id=event_id, student=request.user.student)
                if event.parent_event_id == event.id:
                    # Delete all recurring instances
                    StudentPersonalEvent.objects.filter(parent_event_id=event.id).delete()
                else:
                    event.delete()
                return JsonResponse({'status': 'success'})
            except StudentPersonalEvent.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Event not found.'})
        elif hasattr(request.user, 'faculty'):
            try:
                event = FacultyPersonalEvent.objects.get(id=event_id, faculty=request.user.faculty)
                if event.parent_event_id == event.id:
                    # Delete all recurring instances
                    FacultyPersonalEvent.objects.filter(parent_event_id=event.id).delete()
                else:
                    event.delete()
                return JsonResponse({'status': 'success'})
            except FacultyPersonalEvent.DoesNotExist:
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
                student_name = request.user.get_full_name() or request.user.username
                Notification.objects.create(
                    recipient=lecturer.staff,
                    message=f"New meeting request from {student_name}: '{meeting_request.title}'.",
                    content_type=ContentType.objects.get_for_model(meeting_request),
                    object_id=meeting_request.id,
                )
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
        # Data cleanup: Remove any registration records with empty IDs that cause template errors
        RegisteredUnit.objects.filter(id='', student=request.user.student).delete()
        
        units_QS = BookedUnit.objects.filter(
            lecturer__department=request.user.student.department,
            students_course=request.user.student.course,
            year_of_study=request.user.student.year,
            semester=request.user.student.semester,
        ).exclude(id='')
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
                register_unit, created = RegisteredUnit.objects.get_or_create(    
                    unit=unit_obj,
                    student=request.user.student,
                    defaults={'is_registered': True}
                )

                if not created:
                    messages.warning(request, 'Selected unit already registered!')
                else:
                    messages.success(request, 'Unit successfully registered!')
                return redirect('unit_registration', student_id)
        except RegisteredUnit.DoesNotExist:
            messages.error(request, 'Unknown error occured! Contact system administrator')
            return redirect('unit_registration', student_id)

@login_required(login_url='login')
def unregister_unit(request, student_id, unit_id):
    try:
        reg_unit = RegisteredUnit.objects.get(id=unit_id, student=request.user.student)
        reg_unit.delete()
        messages.success(request, 'Unit successfully unregistered!')
    except RegisteredUnit.DoesNotExist:
        messages.error(request, 'Unit record not found!')
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
        ).order_by('-lecture_date', 'start_time', 'unit_name__course__name')


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
            confirmation.status = 'completed'
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
            unit_name__registeredunit__student=request.user.student, # Filter by units registered by the student
        ).select_related(
            'lecturer__staff',
            'unit_name__course',
            'lecture_hall'
        ).order_by('lecture_date', 'start_time', 'unit_name__course__name')

        available_rooms = ['A110', 'A111', 'A112', 'B110', 'B111', 'B112']
        allocated_rooms = {} # (date, start_time, end_time) -> set of rooms

        lectures_list = list(lectures_QS) # To be able to modify items

        for lecture in lectures_list:
            if not lecture.lecture_hall:
                timeslot = (lecture.lecture_date, lecture.start_time, lecture.end_time)
                
                if timeslot not in allocated_rooms:
                    allocated_rooms[timeslot] = set()

                used_rooms = allocated_rooms[timeslot]
                
                available_for_slot = [room for room in available_rooms if room not in used_rooms]

                if available_for_slot:
                    assigned_room = random.choice(available_for_slot)
                    lecture.assigned_room = assigned_room
                    allocated_rooms[timeslot].add(assigned_room)
                else:
                    # This case happens if more lectures are in a timeslot than available rooms
                    lecture.assigned_room = "No room available"

        context = {'scheduled_lectures': lectures_list}
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
@method_decorator(user_passes_test(lambda user: user.is_faculty), name='get')
class FacultyDashboardView(View):
    template_name = 'dashboard/faculty/homepage.html'

    def get(self, request, *args, **kwargs):
        current_date = dt.now().strftime('%Y-%m-%d')
        total_booked_units = BookedUnit.objects.filter(lecturer=request.user.faculty).exclude(id='').count()
        scheduled_lectures_QS = Lecture.objects.filter(lecturer=request.user.faculty, lecture_date=current_date).order_by('lecture_date', 'start_time')
        pending_requests_count = MeetingRequest.objects.filter(lecturer=request.user.faculty, status='pending').count()

        # check for lectures before current date
        past_lectures_qs = Lecture.objects.filter(is_taught=False, lecture_date__lte=current_date)
        for _lecture in past_lectures_qs:   # iterate through all lectures in the queryset
            get_lecture = Lecture.objects.get(id=_lecture.id)   # get each lecture in the qs using their id
            if get_lecture.is_taught is False:
                get_lecture.is_taught = True    # if the lecture's "is_taught" is False change it to True.
                get_lecture.save()
        
        # Get all lectures for the calendar view - ONLY LECTURES
        all_lectures = Lecture.objects.filter(lecturer=request.user.faculty)
        
        lecture_events = []
        for event in all_lectures:
            lecture_events.append({
                'id': event.id,
                'title': str(event.unit_name.course.name),
                'start': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.start_time.strftime('%H:%M:%S'),
                'end': event.lecture_date.strftime('%Y-%m-%d') + 'T' + event.end_time.strftime('%H:%M:%S'),
                'event_type': 'lecture',
                'description': '',
                'status': event.status,
                'location': event.lecture_hall.name if event.lecture_hall else 'TBA',
                'backgroundColor': '#f56954',
                'borderColor': '#f56954',
            })

        # Smart recommendations: faculty's units with no upcoming lectures in the next 30 days
        from datetime import date, timedelta as td
        today = date.today()
        upcoming_cutoff = today + td(days=30)
        all_booked = BookedUnit.objects.filter(lecturer=request.user.faculty).select_related('course')
        units_to_schedule = [
            u for u in all_booked
            if not Lecture.objects.filter(
                unit_name=u, lecture_date__gte=today, lecture_date__lte=upcoming_cutoff
            ).exists()
        ][:5]

        context = {
            'TotalBookedUnits': total_booked_units,
            'scheduled_lectures': scheduled_lectures_QS,
            'events': json.dumps(lecture_events),
            'pending_requests_count': pending_requests_count,
            'personal_event_form': FacultyPersonalEventForm(),
            'units_to_schedule': units_to_schedule,
        }
        return render(request, self.template_name, context)

@login_required(login_url='login')
def approve_meeting_request(request, request_id):
    if request.method != 'POST':
        return redirect('manage_meeting_requests')
    try:
        meeting_request = MeetingRequest.objects.get(id=request_id)
        if request.user.faculty != meeting_request.lecturer:
            messages.error(request, 'You are not authorized to approve this request.')
            return redirect('manage_meeting_requests')

        remarks = request.POST.get('remarks', '').strip()
        meeting_request.status = 'approved'
        meeting_request.lecturer_remarks = remarks or None
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

        # Notify student with result and any remarks
        note_suffix = f' Lecturer note: "{remarks}"' if remarks else ''
        Notification.objects.create(
            recipient=meeting_request.student.student_name,
            message=(
                f'Your meeting request "{meeting_request.title}" with '
                f'{meeting_request.lecturer.staff.get_full_name()} has been approved. '
                f'Time: {meeting_request.start_time.strftime("%d %b %Y %H:%M")} – '
                f'{meeting_request.end_time.strftime("%H:%M")} at {meeting_request.location}.'
                f'{note_suffix}'
            ),
            content_object=meeting_request,
        )
        messages.success(request, 'Meeting request approved and student notified.')
    except MeetingRequest.DoesNotExist:
        messages.error(request, 'Meeting request not found.')
    return redirect('manage_meeting_requests')


@login_required(login_url='login')
def reject_meeting_request(request, request_id):
    if request.method != 'POST':
        return redirect('manage_meeting_requests')
    try:
        meeting_request = MeetingRequest.objects.get(id=request_id)
        if request.user.faculty != meeting_request.lecturer:
            messages.error(request, 'You are not authorized to reject this request.')
            return redirect('manage_meeting_requests')

        remarks = request.POST.get('remarks', '').strip()
        meeting_request.status = 'rejected'
        meeting_request.lecturer_remarks = remarks or None
        meeting_request.save()

        # Notify student
        note_suffix = f' Reason: "{remarks}"' if remarks else ''
        Notification.objects.create(
            recipient=meeting_request.student.student_name,
            message=(
                f'Your meeting request "{meeting_request.title}" with '
                f'{meeting_request.lecturer.staff.get_full_name()} has been rejected.'
                f'{note_suffix}'
            ),
            content_object=meeting_request,
        )
        messages.success(request, 'Meeting request rejected and student notified.')
    except MeetingRequest.DoesNotExist:
        messages.error(request, 'Meeting request not found.')
    return redirect('manage_meeting_requests')


@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='get')
class ManageMeetingRequestsView(View):
    template_name = 'dashboard/faculty/manage_requests.html'

    def get(self, request, *args, **kwargs):
        base_qs = MeetingRequest.objects.filter(lecturer=request.user.faculty).order_by('-date_created')
        context = {
            'pending_requests': base_qs.filter(status='pending'),
            'approved_requests': base_qs.filter(status='approved'),
            'rejected_requests': base_qs.filter(status='rejected'),
            'modified_requests': base_qs.filter(status='modified'),
            'cancelled_requests': base_qs.filter(status='cancelled'),
        }
        return render(request, self.template_name, context)


@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is True), name='get')
class StudentMeetingRequestsView(View):
    """Student view to track all their meeting requests and statuses."""
    template_name = 'dashboard/students/meeting_requests.html'

    def get(self, request, *args, **kwargs):
        all_requests = MeetingRequest.objects.filter(
            student=request.user.student
        ).order_by('-date_created')
        context = {'all_requests': all_requests}
        return render(request, self.template_name, context)


@login_required(login_url='login')
def cancel_meeting_request(request, request_id):
    """Allow a student to cancel their own pending meeting request."""
    if request.method != 'POST':
        return redirect('student_meeting_requests')
    try:
        meeting_request = MeetingRequest.objects.get(id=request_id, student=request.user.student)
        if meeting_request.status not in ('pending', 'modified'):
            messages.error(request, 'Only pending or modified requests can be cancelled.')
            return redirect('student_meeting_requests')
        meeting_request.status = 'cancelled'
        meeting_request.save()

        # Notify lecturer
        Notification.objects.create(
            recipient=meeting_request.lecturer.staff,
            message=(
                f'{request.user.get_full_name()} has cancelled their meeting request '
                f'"{meeting_request.title}" scheduled for '
                f'{meeting_request.start_time.strftime("%d %b %Y %H:%M")}.'
            ),
            content_object=meeting_request,
        )
        messages.success(request, 'Meeting request cancelled.')
    except MeetingRequest.DoesNotExist:
        messages.error(request, 'Meeting request not found.')
    return redirect('student_meeting_requests')


@method_decorator(user_passes_test(lambda user: hasattr(user, 'faculty')), name='dispatch')
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

            # Create recurring instances
            create_recurring_instances(new_scheduled_lecture)

            # Create a notification for the lecturer
            Notification.objects.create(
                recipient=request.user,
                message=f"You have successfully scheduled a lecture (and recurrences if any) for {new_scheduled_lecture.unit_name} starting {new_scheduled_lecture.lecture_date} at {new_scheduled_lecture.start_time}.",
                content_object=new_scheduled_lecture
            )

            messages.success(request, 'Lecture successfully scheduled!')
            return redirect('faculty_homepage')
        else:
            messages.warning(request, 'The form has errors. Please correct them and try again.')
            
            booked_units_QS = BookedUnit.objects.filter(lecturer=staff_id).exclude(id='')
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
@method_decorator(user_passes_test(lambda user: hasattr(user, 'faculty')), name='get')
class AssignUnitsforLecturersView(View):
    form_class = LecturerUnitsBookingForm
    template_name = 'dashboard/faculty/book-units.html'

    def get(self, request, *args, **kwargs):
        booked_units_QS = BookedUnit.objects.filter(lecturer__department=request.user.faculty.department)
        form = self.form_class()

        context = {
            'LecturersUnitsBookingForm': form,
            'booked_units': booked_units_QS
        }
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)

        if form.is_valid():
            lecturer = form.cleaned_data['lecturer']
            courses = form.cleaned_data['courses'] # This will be a queryset of Course objects
            students_course = form.cleaned_data['students_course']
            year_of_study = form.cleaned_data['year_of_study']
            semester = form.cleaned_data['semester']

            course_names = [name.strip() for name in form.cleaned_data['courses'].split(',') if name.strip()]

            for course_name in course_names:
                try:
                    course = Course.objects.get(name=course_name)
                except Course.DoesNotExist:
                    base_code = course_name[:10].upper()
                    code, suffix = base_code, 1
                    while Course.objects.filter(code=code).exists():
                        code = f"{base_code[:8]}{suffix:02d}"
                        suffix += 1
                    course = Course.objects.create(name=course_name, code=code)
                
                # Check if a similar BookedUnit already exists to prevent duplicates
                existing_booked_unit = BookedUnit.objects.filter(
                    lecturer=lecturer,
                    course=course,
                    students_course=students_course,
                    year_of_study=year_of_study,
                    semester=semester
                ).first()

                if existing_booked_unit:
                    messages.warning(request, f'Course "{course.name}" for {students_course} {year_of_study} {semester} is already assigned to {lecturer}.')
                else:
                    BookedUnit.objects.create(
                        lecturer=lecturer,
                        course=course,
                        students_course=students_course,
                        year_of_study=year_of_study,
                        semester=semester,
                        booking_date=timezone.now()
                    )
                    messages.success(request, f'Course "{course.name}" assigned to {lecturer} successfully!')
            
            # Redirect to the same page to allow further assignments or view updated list
            return redirect('assign_units') # Removed staff_id from redirect
        
        # If form is not valid, re-render the page with errors
        booked_units_QS = BookedUnit.objects.filter(lecturer__department=request.user.faculty.department)
        context = {
            'LecturersUnitsBookingForm': form,
            'booked_units': booked_units_QS
        }
        return render(request, self.template_name, context)

@method_decorator(login_required(login_url='login'), name='get')
@method_decorator(user_passes_test(lambda user: (user.is_staff is False or user.is_superuser is False) and user.is_student is False), name='get')
class LecturesDetailView(View):
    template_name = 'dashboard/faculty/lectures.html'

    def get(self, request, staff_name, staff_id, *args, **kwargs):
        scheduled_lectures_QS = Lecture.objects.filter(lecturer=request.user.faculty).order_by('unit_name')

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
@method_decorator(user_passes_test(lambda user: not user.is_student), name='get')
class ViewUnitStudentsView(View):
    template_name = 'dashboard/faculty/unit_students.html'

    def get(self, request, unit_id, *args, **kwargs):
        try:
            unit = BookedUnit.objects.get(id=unit_id)
            # Ensure the lecturer accessing this page is the one assigned to the unit or the user is an admin
            if not request.user.is_staff and not request.user.is_superuser:
                if unit.lecturer != request.user.faculty:
                    messages.error(request, "You are not authorized to view students for this unit.")
                    return redirect('view_faculty_lectures', staff_id=request.user.faculty.id, staff_name=request.user.faculty)

            registered_students = RegisteredUnit.objects.filter(unit=unit).select_related('student__student_name')
            lectures_for_unit = Lecture.objects.filter(unit_name=unit).order_by('lecture_date', 'start_time')

            lecture_events = []
            seen_lectures = set()
            for lecture in lectures_for_unit:
                event_tuple = (lecture.lecture_date, lecture.start_time)
                if event_tuple not in seen_lectures:
                    lecture_events.append(lecture)
                    seen_lectures.add(event_tuple)

            attendance_data = []
            for reg_unit in registered_students:
                student = reg_unit.student
                student_attendance = {
                    'student': student,
                    'attendance': []
                }
                for lecture_event in lecture_events:
                    attended = Lecture.objects.filter(
                        unit_name=unit,
                        lecture_date=lecture_event.lecture_date,
                        start_time=lecture_event.start_time,
                        student=student,
                        is_attending=True
                    ).exists()
                    student_attendance['attendance'].append(attended)
                attendance_data.append(student_attendance)

            context = {
                'unit': unit,
                'attendance_data': attendance_data,
                'lecture_events': lecture_events,
            }
            return render(request, self.template_name, context)
        except BookedUnit.DoesNotExist:
            messages.error(request, "The selected unit does not exist.")
            if not request.user.is_staff and not request.user.is_superuser:
                return redirect('view_faculty_lectures', staff_id=request.user.faculty.id, staff_name=request.user.faculty)
            else:
                return redirect('admin_dashboard') # Or some other admin page


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

            # Get student's registered units to accurately filter lectures.
            registered_units = RegisteredUnit.objects.filter(student=student)
            booked_units = [reg_unit.unit for reg_unit in registered_units]
            student_lectures = Lecture.objects.filter(unit_name__in=booked_units)

            for event in student_lectures:
                event_data.append({
                    'title': str(event.unit_name.course.name),
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
            Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
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
            'id': n.id,
            'message': n.message,
            'is_event_reminder': False,
            'event_start_time': None,
            'event_title': None,
        }
        if n.content_object:
            if isinstance(n.content_object, Lecture):
                item['is_event_reminder'] = True
                item['event_start_time'] = n.content_object.start_time.strftime('%H:%M')
                item['event_title'] = str(n.content_object.unit_name.course.name)
            elif isinstance(n.content_object, MeetingRequest):
                item['is_event_reminder'] = True
                item['event_start_time'] = n.content_object.start_time.strftime('%H:%M')
                item['event_title'] = n.content_object.title
        data.append(item)
    return JsonResponse(data, safe=False)


@login_required(login_url='login')
def unread_notifications_api(request):
    unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-date_created')
    notifications_data = [
        {
            'id': n.id,
            'message': n.message,
            'date_created': n.date_created.isoformat(),
        }
        for n in unread_notifications
    ]
    return JsonResponse({
        'count': unread_notifications.count(),
        'notifications': notifications_data
    })


@login_required(login_url='login')
def sign_in_to_event(request, event_type, event_id):
    if request.method == 'POST':
        try:
            if event_type == 'personal':
                if request.user.is_student:
                    event = StudentPersonalEvent.objects.get(id=event_id, student=request.user.student)
                else:
                    event = FacultyPersonalEvent.objects.get(id=event_id, faculty=request.user.faculty)
                event.is_signed_in = True
                event.save()
            elif event_type == 'meeting':
                if request.user.is_student:
                    event = MeetingRequest.objects.get(id=event_id, student=request.user.student)
                else:
                    event = MeetingRequest.objects.get(id=event_id, lecturer=request.user.faculty)
                event.is_signed_in = True
                event.save()
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid event type'}, status=400)
            
            return JsonResponse({'status': 'success'})
        except (StudentPersonalEvent.DoesNotExist, FacultyPersonalEvent.DoesNotExist, MeetingRequest.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Event not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


@login_required(login_url='login')
def personal_report(request):
    """
    Generates a personal report for the logged-in user (Student or Faculty).
    Includes counts for completed, missed, and total events.
    """
    user = request.user
    context = {}

    if user.is_student:
        student = user.student
        
        # 1. Lectures Stats (Shared event status)
        registered_units = RegisteredUnit.objects.filter(student=student)
        booked_units = [reg_unit.unit for reg_unit in registered_units]
        lecture_qs = Lecture.objects.filter(unit_name__in=booked_units)
        
        lecture_stats = {
            'total': lecture_qs.count(),
            'completed': lecture_qs.filter(status='completed').count(),
            'missed': lecture_qs.filter(status='missed').count(),
            'scheduled': lecture_qs.filter(status='scheduled').count(),
        }
        
        # 2. Personal Events Stats
        personal_qs = StudentPersonalEvent.objects.filter(student=student)
        personal_stats = {
            'total': personal_qs.count(),
            'completed': personal_qs.filter(status='completed').count(),
            'missed': personal_qs.filter(status='missed').count(),
            'pending': personal_qs.filter(status='pending').count(),
        }
        
        # 3. Meeting Requests Stats
        meeting_qs = MeetingRequest.objects.filter(student=student)
        meeting_stats = {
            'total': meeting_qs.count(),
            'completed': meeting_qs.filter(status='completed').count(),
            'missed': meeting_qs.filter(status='missed').count(),
            'approved': meeting_qs.filter(status='approved').count(),
            'pending': meeting_qs.filter(status='pending').count(),
            'rejected': meeting_qs.filter(status='rejected').count(),
        }
        
        context.update({
            'user_type': 'Student',
            'base_template': 'dashboard/students/base.html',
            'lecture_stats': lecture_stats,
            'personal_stats': personal_stats,
            'meeting_stats': meeting_stats,
            'total_completed': lecture_stats['completed'] + personal_stats['completed'] + meeting_stats['completed'],
            'total_missed': lecture_stats['missed'] + personal_stats['missed'] + meeting_stats['missed'],
        })

    elif hasattr(user, 'faculty'):
        faculty = user.faculty
        
        # 1. Lectures Stats
        lecture_qs = Lecture.objects.filter(lecturer=faculty)
        lecture_stats = {
            'total': lecture_qs.count(),
            'completed': lecture_qs.filter(status='completed').count(),
            'missed': lecture_qs.filter(status='missed').count(),
            'scheduled': lecture_qs.filter(status='scheduled').count(),
        }
        
        # 2. Personal Events Stats
        personal_qs = FacultyPersonalEvent.objects.filter(faculty=faculty)
        personal_stats = {
            'total': personal_qs.count(),
            'completed': personal_qs.filter(status='completed').count(),
            'missed': personal_qs.filter(status='missed').count(),
            'pending': personal_qs.filter(status='pending').count(),
        }
        
        # 3. Meeting Requests Stats (Received)
        meeting_qs = MeetingRequest.objects.filter(lecturer=faculty)
        meeting_stats = {
            'total': meeting_qs.count(),
            'completed': meeting_qs.filter(status='completed').count(),
            'missed': meeting_qs.filter(status='missed').count(),
            'approved': meeting_qs.filter(status='approved').count(),
            'pending': meeting_qs.filter(status='pending').count(),
            'rejected': meeting_qs.filter(status='rejected').count(),
        }
        
        context.update({
            'user_type': 'Faculty',
            'base_template': 'dashboard/faculty/base.html',
            'lecture_stats': lecture_stats,
            'personal_stats': personal_stats,
            'meeting_stats': meeting_stats,
            'total_completed': lecture_stats['completed'] + personal_stats['completed'] + meeting_stats['completed'],
            'total_missed': lecture_stats['missed'] + personal_stats['missed'] + meeting_stats['missed'],
        })

    return render(request, 'dashboard/reports.html', context)


# ── Event Comments ────────────────────────────────────────────────────────────

def _get_ct_and_obj(model_label, object_id):
    """
    Resolve a short model label ('lecture', 'studentpersonalevent', …)
    to a (ContentType, event_object) pair.  Returns (None, None) on failure.
    """
    MODEL_MAP = {
        'lecture': Lecture,
        'studentpersonalevent': StudentPersonalEvent,
        'facultypersonalevent': FacultyPersonalEvent,
        'meetingrequest': MeetingRequest,
    }
    model_cls = MODEL_MAP.get(model_label.lower())
    if model_cls is None:
        return None, None
    try:
        obj = model_cls.objects.get(id=object_id)
        ct = ContentType.objects.get_for_model(model_cls)
        return ct, obj
    except model_cls.DoesNotExist:
        return None, None


@login_required(login_url='login')
def list_event_comments(request, model_label, object_id):
    """GET — return all comments for the given event as JSON."""
    ct, _ = _get_ct_and_obj(model_label, object_id)
    if ct is None:
        return JsonResponse({'status': 'error', 'message': 'Event not found.'}, status=404)

    comments = EventComment.objects.filter(content_type=ct, object_id=object_id)
    is_faculty_or_admin = hasattr(request.user, 'faculty') or request.user.is_staff or request.user.is_superuser

    data = []
    for c in comments:
        data.append({
            'id': c.id,
            'author': c.author.get_full_name() or c.author.username,
            'content': c.content,
            'is_pinned': c.is_pinned,
            'date_created': c.date_created.strftime('%d %b %Y %H:%M'),
            'is_own': c.author_id == request.user.id,
            'can_pin': is_faculty_or_admin,
        })
    return JsonResponse({'status': 'success', 'comments': data})


@login_required(login_url='login')
def add_event_comment(request, model_label, object_id):
    """POST — add a comment to an event."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    ct, event_obj = _get_ct_and_obj(model_label, object_id)
    if ct is None:
        return JsonResponse({'status': 'error', 'message': 'Event not found.'}, status=404)

    content = (request.POST.get('content') or '').strip()
    if not content:
        return JsonResponse({'status': 'error', 'message': 'Comment cannot be empty.'})

    comment = EventComment.objects.create(
        author=request.user,
        content=content,
        content_type=ct,
        object_id=object_id,
    )
    return JsonResponse({
        'status': 'success',
        'comment': {
            'id': comment.id,
            'author': request.user.get_full_name() or request.user.username,
            'content': comment.content,
            'is_pinned': comment.is_pinned,
            'date_created': comment.date_created.strftime('%d %b %Y %H:%M'),
            'is_own': True,
            'can_pin': hasattr(request.user, 'faculty'),
        },
    })


@login_required(login_url='login')
def pin_event_comment(request, comment_id):
    """POST — toggle pin status on a comment (faculty / admin only)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    if not (hasattr(request.user, 'faculty') or request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'status': 'error', 'message': 'Only faculty or admins can pin comments.'}, status=403)

    try:
        comment = EventComment.objects.get(id=comment_id)
    except EventComment.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Comment not found.'}, status=404)

    comment.is_pinned = not comment.is_pinned
    comment.save()

    # Send "important announcement" notifications when pinning
    if comment.is_pinned:
        event_obj = comment.content_object
        msg_prefix = f'[Important Announcement] {comment.author.get_full_name() or comment.author.username}: {comment.content[:120]}'

        if isinstance(event_obj, Lecture):
            # Notify all students registered for this lecture's unit
            registered = RegisteredUnit.objects.filter(unit=event_obj.unit_name).select_related('student__student_name')
            for reg in registered:
                Notification.objects.create(
                    recipient=reg.student.student_name,
                    message=f'{msg_prefix} (Lecture: {event_obj.unit_name.course.name}, {event_obj.lecture_date})',
                    content_object=comment,
                )

        elif isinstance(event_obj, MeetingRequest):
            # Notify the other party
            recipients = []
            if request.user == event_obj.lecturer.staff:
                recipients.append(event_obj.student.student_name)
            else:
                recipients.append(event_obj.lecturer.staff)
            for recipient in recipients:
                Notification.objects.create(
                    recipient=recipient,
                    message=f'{msg_prefix} (Meeting: {event_obj.title})',
                    content_object=comment,
                )

    return JsonResponse({'status': 'success', 'is_pinned': comment.is_pinned})


@login_required(login_url='login')
def delete_event_comment(request, comment_id):
    """POST — delete a comment (author or faculty/admin)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    try:
        comment = EventComment.objects.get(id=comment_id)
    except EventComment.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Comment not found.'}, status=404)

    is_author = comment.author_id == request.user.id
    is_faculty = hasattr(request.user, 'faculty')
    if not (is_author or is_faculty):
        return JsonResponse({'status': 'error', 'message': 'Not authorised.'}, status=403)

    comment.delete()
    return JsonResponse({'status': 'success'})
