from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.contrib import messages
from campus.models import Notification
from .forms import BookedUnitForm

@method_decorator(login_required(login_url='login'), name='dispatch')
@method_decorator(user_passes_test(lambda u: u.is_admin), name='dispatch')
class AdminAssignUnitView(View):
    form_class = BookedUnitForm
    template_name = 'new_features/admin_assign_unit.html'

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            booked_unit = form.save()
            course_name = booked_unit.course.name

            # Create a notification for the lecturer
            Notification.objects.create(
                recipient=booked_unit.lecturer.staff,
                message=f"A new unit '{course_name}' has been assigned to you by an administrator. You can now schedule lectures for it.",
                content_object=booked_unit
            )

            messages.success(request, f"Unit '{course_name}' assigned to {booked_unit.lecturer.staff.get_full_name()} successfully.")
            return redirect('admin_assign_unit')

        return render(request, self.template_name, {'form': form})