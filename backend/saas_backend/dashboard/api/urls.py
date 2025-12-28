from django.urls import path
from .views import DashboardTodayView

urlpatterns = [
    path("dashboard/today/", DashboardTodayView.as_view(), name="dashboard-today"),
]
