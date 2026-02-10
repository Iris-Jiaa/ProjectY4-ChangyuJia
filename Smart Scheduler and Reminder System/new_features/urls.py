from django.urls import path
from .views import AdminAssignUnitView

urlpatterns = [
    path('admin/assign-unit/', AdminAssignUnitView.as_view(), name='admin_assign_unit'),
]
