from django.urls import path
from .views import MeView, GoogleLoginView

urlpatterns = [
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/google/", GoogleLoginView.as_view(), name="auth-google"),
]
