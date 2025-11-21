from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import InternalOrderViewSet

router = DefaultRouter()
router.register(r"orders", InternalOrderViewSet, basename="orders")

urlpatterns = [
    path("", include(router.urls)),
]
