"""Routes for project intake and the initial informational pages."""

from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("trydemo/", views.try_demo, name="trydemo"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("health/", views.health, name="health"),
]
