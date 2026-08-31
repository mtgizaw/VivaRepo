"""Routes for project intake and the initial informational pages."""

from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("dashboard/", views.account_dashboard, name="dashboard"),
    path("trydemo/", views.try_demo, name="trydemo"),
    path(
        "repositories/upload/",
        views.upload_repository,
        name="upload_repository",
    ),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("health/", views.health, name="health"),
]
