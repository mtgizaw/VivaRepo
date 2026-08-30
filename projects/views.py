"""Views for the VivaRepo web experience and local authentication."""

from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
import plotly.graph_objects as go
from plotly.io import to_html

from .forms import EmailLoginForm, SignupForm


User = get_user_model()


def build_account_count_chart(account_count: int) -> str:
    """Return an embeddable Plotly indicator for the current account total."""
    figure = go.Figure(
        go.Indicator(
            mode="number",
            value=account_count,
            number={
                "font": {"color": "#101a32", "size": 88},
                "valueformat": ",d",
            },
            title={
                "font": {"color": "#596983", "size": 18},
                "text": "Registered accounts",
            },
        )
    )
    figure.update_layout(
        autosize=True,
        height=280,
        margin={"b": 20, "l": 20, "r": 20, "t": 40},
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        font={
            "family": (
                "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "
                "'Segoe UI', sans-serif"
            )
        },
    )
    return to_html(
        figure,
        config={
            "displayModeBar": False,
            "responsive": True,
        },
        div_id="account-count-chart",
        full_html=False,
        include_plotlyjs="cdn",
    )


def home(request: HttpRequest) -> HttpResponse:
    """Render the product landing page."""
    return render(request, "projects/home.html")


def about(request: HttpRequest) -> HttpResponse:
    """Explain the purpose and boundaries of VivaRepo."""
    return render(request, "projects/about.html")


def account_dashboard(request: HttpRequest) -> HttpResponse:
    """Show the live number of accounts in Django's configured user model."""
    account_count = User.objects.count()
    return render(
        request,
        "projects/dashboard.html",
        {
            "account_count": account_count,
            "account_count_chart": build_account_count_chart(account_count),
        },
    )


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
