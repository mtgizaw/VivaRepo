"""Root URL configuration for VivaRepo."""

from django.urls import include, path

urlpatterns = [
    path("", include("projects.urls")),
]

