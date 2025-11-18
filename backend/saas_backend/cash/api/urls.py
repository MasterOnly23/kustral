# cash/api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DailyCashViewSet

router = DefaultRouter()
router.register(r"cash/daily", DailyCashViewSet, basename="daily-cash")

urlpatterns = [
    path("", include(router.urls)),
]
