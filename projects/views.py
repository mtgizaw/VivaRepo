"""Views for the VivaRepo web experience and local authentication."""

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import EmailLoginForm, SignupForm


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
    """Create a local account and start an authenticated session."""
    if request.user.is_authenticated:
        return redirect("projects:home")

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        return redirect("projects:home")

    return render(request, "projects/signup.html", {"form": form})


def login_view(request: HttpRequest) -> HttpResponse:
    """Authenticate a local account using its email address."""
    if request.user.is_authenticated:
        return redirect("projects:home")

    form = EmailLoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        if not form.cleaned_data["remember_me"]:
            request.session.set_expiry(0)
        return redirect("projects:home")

    return render(request, "projects/login.html", {"form": form})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    """End the current authenticated session."""
    auth_logout(request)
    return redirect("projects:home")


def health(request: HttpRequest) -> JsonResponse:
    """Provide a lightweight readiness check for local development."""
    return JsonResponse({"status": "ok", "service": "vivarepo"})
