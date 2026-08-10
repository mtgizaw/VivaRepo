"""Views for the initial VivaRepo web experience."""

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """Render the product landing page."""
    return render(request, "projects/home.html")

def about(request: HttpRequest) -> HttpResponse:
    """Explain the purpose and boundaries of VivaRepo."""
    return render(request, "projects/about.html")

def try_demo(request: HttpRequest) -> HttpResponse:
    """Render the demo page for users to explore a sample repository."""
    return render(request, "projects/trydemo.html")

def signup(request: HttpRequest) -> HttpResponse:
    """Render the account registration page."""
    return render(request, "projects/signup.html")

def login(request: HttpRequest) -> HttpResponse:
    """Render the account login page."""
    return render(request, "projects/login.html")

def health(request: HttpRequest) -> JsonResponse:
    """Provide a lightweight readiness check for local development."""
    return JsonResponse({"status": "ok", "service": "vivarepo"})
