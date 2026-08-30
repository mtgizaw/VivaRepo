"""Root URL configuration for VivaRepo."""

from django.urls import include, path

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("", include("projects.urls")),
]

