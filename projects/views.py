"""Views for the VivaRepo web experience and local authentication."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
import plotly.graph_objects as go
from plotly.io import to_html

from ai.repository_questions import (
    QuestionGenerationError,
    generate_questions_for_repository,
)
from ai.answer_evaluation import EvaluationError, evaluate_assessment_answers
from assessments.models import (
    AssessmentSubmission,
    FreeResponseQuestion,
    QuestionSet,
    SubmittedAnswer,
)

from .forms import (
    AssessmentAnswerForm,
    EmailLoginForm,
    RepositoryArchiveReplacementForm,
    RepositoryUploadForm,
    SignupForm,
)
from .models import Repository


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
    """Show aggregate VivaRepo account, repository, and question metrics."""
    account_count = User.objects.count()
    repository_count = Repository.objects.count()
    question_count = FreeResponseQuestion.objects.count()
    topic_tallies = list(
        FreeResponseQuestion.objects.exclude(focus_area="")
        .values("focus_area")
        .annotate(question_count=Count("id"))
        .order_by("-question_count", "focus_area")
    )
    return render(
        request,
        "projects/dashboard.html",
        {
            "account_count": account_count,
            "repository_count": repository_count,
            "question_count": question_count,
            "topic_tallies": topic_tallies,
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


def _safe_next_url(request: HttpRequest) -> str | None:
    """Return a local post-authentication destination, when one was supplied."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


def login_view(request: HttpRequest) -> HttpResponse:
    """Authenticate a local account using its email address."""
    next_url = _safe_next_url(request)
    if request.user.is_authenticated:
        return redirect(next_url or "projects:home")

    form = EmailLoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        if not form.cleaned_data["remember_me"]:
            request.session.set_expiry(0)
        return redirect(next_url or "projects:home")

    return render(
        request,
        "projects/login.html",
        {"form": form, "next": next_url or ""},
    )


@login_required
def upload_repository(request: HttpRequest) -> HttpResponse:
    """Accept a ZIP archive and associate it with the signed-in user."""
    form = RepositoryUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        repository = form.save(commit=False)
        repository.uploaded_by = request.user
        repository.original_filename = form.cleaned_data["archive"].name
        repository.size_bytes = form.cleaned_data["archive"].size
        repository.source_context = form.repository_context
        repository.save()
        messages.success(
            request,
            f'"{repository.name}" was uploaded and is ready for analysis.',
        )
        return redirect("projects:upload_repository")

    repositories = request.user.repositories.select_related("question_set").all()
    return render(
        request,
        "projects/upload_repository.html",
        {"form": form, "repositories": repositories},
    )


@login_required
@require_POST
def delete_repository(request: HttpRequest, repository_id: int) -> HttpResponse:
    """Delete a repository owned by the signed-in user and its stored archive."""
    repository = get_object_or_404(
        Repository,
        pk=repository_id,
        uploaded_by=request.user,
    )
    repository_name = repository.name
    archive_name = repository.archive.name
    archive_storage = repository.archive.storage

    repository.delete()
    if archive_name:
        archive_storage.delete(archive_name)

    messages.success(request, f'"{repository_name}" was removed.')
    return redirect("projects:upload_repository")


@login_required
def repository_detail(request: HttpRequest, repository_id: int) -> HttpResponse:
    """Show a user's repository and its generated free-response questions."""
    repository = get_object_or_404(
        Repository,
        pk=repository_id,
        uploaded_by=request.user,
    )
    question_set = getattr(repository, "question_set", None)
    questions = list(
        question_set.questions.all()
        if question_set and question_set.status == QuestionSet.Status.COMPLETE
        else []
    )
    submission = getattr(question_set, "submission", None) if question_set else None
    submitted_answers = {
        answer.question_id: answer
        for answer in submission.answers.select_related("question").all()
    } if submission else {}
    answer_form = None
    answer_fields = []
    evaluation_items = []
    if questions and not (
        submission and submission.status == AssessmentSubmission.Status.COMPLETE
    ):
        answer_form = AssessmentAnswerForm(
            questions,
            initial_answers={
                question_id: answer.response
                for question_id, answer in submitted_answers.items()
            },
        )
        answer_fields = [
            (question, answer_form[f"question_{question.pk}"])
            for question in questions
        ]
    elif submission and submission.status == AssessmentSubmission.Status.COMPLETE:
        feedback_by_position = {
            item["question_number"]: item
            for item in submission.question_feedback
        }
        evaluation_items = [
            {
                "question": question,
                "answer": submitted_answers.get(question.pk),
                "feedback": feedback_by_position.get(question.position),
            }
            for question in questions
        ]
    zip_read_failed = bool(
        question_set
        and question_set.status == QuestionSet.Status.FAILED
        and question_set.error_message.startswith(
            "VivaRepo could not read this repository ZIP"
        )
    )
    return render(
        request,
        "projects/repository_detail.html",
        {
            "repository": repository,
            "question_set": question_set,
            "questions": questions,
            "submission": submission,
            "answer_form": answer_form,
            "answer_fields": answer_fields,
            "evaluation_items": evaluation_items,
            "zip_read_failed": zip_read_failed,
        },
    )


@login_required
@require_POST
def submit_assessment_answers(
    request: HttpRequest,
    repository_id: int,
) -> HttpResponse:
    """Persist all five learner answers and generate a detailed evaluation."""
    repository = get_object_or_404(
        Repository,
        pk=repository_id,
        uploaded_by=request.user,
    )
    question_set = get_object_or_404(
        QuestionSet,
        repository=repository,
        status=QuestionSet.Status.COMPLETE,
    )
    questions = list(question_set.questions.all())
    if len(questions) != 5:
        messages.error(request, "This assessment does not contain five questions yet.")
        return redirect("projects:repository_detail", repository_id=repository.pk)

    existing_submission = getattr(question_set, "submission", None)
    if (
        existing_submission
        and existing_submission.status == AssessmentSubmission.Status.COMPLETE
    ):
        return redirect("projects:repository_detail", repository_id=repository.pk)
    if (
        existing_submission
        and existing_submission.status == AssessmentSubmission.Status.EVALUATING
    ):
        messages.info(request, "Your answers are already being evaluated.")
        return redirect("projects:repository_detail", repository_id=repository.pk)

    form = AssessmentAnswerForm(questions, request.POST)
    if not form.is_valid():
        submission = existing_submission
        submitted_answers = {
            answer.question_id: answer
            for answer in submission.answers.all()
        } if submission else {}
        return render(
            request,
            "projects/repository_detail.html",
            {
                "repository": repository,
                "question_set": question_set,
                "questions": questions,
                "submission": submission,
                "answer_form": form,
                "answer_fields": [
                    (question, form[f"question_{question.pk}"])
                    for question in questions
                ],
                "evaluation_items": [],
                "zip_read_failed": False,
                "submitted_answers": submitted_answers,
            },
        )

    answers = form.answers_by_question_id()
    submission, _ = AssessmentSubmission.objects.update_or_create(
        question_set=question_set,
        defaults={
            "submitted_by": request.user,
            "status": AssessmentSubmission.Status.EVALUATING,
            "model_name": settings.OPENAI_EVALUATION_MODEL,
            "error_message": "",
        },
    )
    with transaction.atomic():
        for question in questions:
            SubmittedAnswer.objects.update_or_create(
                submission=submission,
                question=question,
                defaults={"response": answers[question.pk]},
            )

    try:
        generated = evaluate_assessment_answers(
            repository,
            question_set,
            answers,
            request.user,
        )
    except EvaluationError as exc:
        submission.status = AssessmentSubmission.Status.FAILED
        submission.error_message = str(exc)
        submission.save(update_fields=("status", "error_message"))
        return redirect("projects:repository_detail", repository_id=repository.pk)

    result = generated.result
    submission.status = AssessmentSubmission.Status.COMPLETE
    submission.overall_score = result["overall_score"]
    submission.overall_summary = result["overall_summary"]
    submission.strengths = result["strengths"]
    submission.weaknesses = result["weaknesses"]
    submission.question_feedback = result["question_feedback"]
    submission.practice_resources = result["practice_resources"]
    submission.model_name = generated.model_name
    submission.response_id = generated.response_id
    submission.error_message = ""
    submission.completed_at = timezone.now()
    submission.save(
        update_fields=(
            "status",
            "overall_score",
            "overall_summary",
            "strengths",
            "weaknesses",
            "question_feedback",
            "practice_resources",
            "model_name",
            "response_id",
            "error_message",
            "completed_at",
        )
    )
    messages.success(request, "Your detailed evaluation is ready.")
    return redirect("projects:repository_detail", repository_id=repository.pk)


@login_required
@require_POST
def replace_repository_archive(
    request: HttpRequest,
    repository_id: int,
) -> HttpResponse:
    """Replace a missing ZIP, persist its source context, and retry generation."""
    repository = get_object_or_404(
        Repository,
        pk=repository_id,
        uploaded_by=request.user,
    )
    question_set = getattr(repository, "question_set", None)
    if question_set and question_set.status == QuestionSet.Status.COMPLETE:
        return redirect("projects:repository_detail", repository_id=repository.pk)

    form = RepositoryArchiveReplacementForm(request.POST, request.FILES)
    if not form.is_valid():
        error_message = next(
            (
                str(error)
                for field_errors in form.errors.values()
                for error in field_errors
            ),
            "Select a valid repository ZIP and try again.",
        )
        messages.error(request, error_message)
        return redirect("projects:repository_detail", repository_id=repository.pk)

    archive = form.cleaned_data["archive"]
    repository.archive = archive
    repository.original_filename = archive.name
    repository.size_bytes = archive.size
    repository.source_context = form.repository_context
    repository.save(
        update_fields=(
            "archive",
            "original_filename",
            "size_bytes",
            "source_context",
        )
    )
    return generate_repository_questions(request, repository.pk)


@login_required
@require_POST
def generate_repository_questions(
    request: HttpRequest,
    repository_id: int,
) -> HttpResponse:
    """Generate and persist one five-question assessment for a repository."""
    repository = get_object_or_404(
        Repository,
        pk=repository_id,
        uploaded_by=request.user,
    )
    question_set, created = QuestionSet.objects.get_or_create(
        repository=repository,
        defaults={
            "generated_by": request.user,
            "model_name": settings.OPENAI_QUESTION_MODEL,
            "status": QuestionSet.Status.GENERATING,
        },
    )
    if not created and question_set.status == QuestionSet.Status.COMPLETE:
        return redirect("projects:repository_detail", repository_id=repository.pk)
    if not created and question_set.status == QuestionSet.Status.GENERATING:
        messages.info(request, "Question generation is already in progress.")
        return redirect("projects:repository_detail", repository_id=repository.pk)

    if not created:
        question_set.status = QuestionSet.Status.GENERATING
        question_set.error_message = ""
        question_set.save(update_fields=("status", "error_message"))

    try:
        generated = generate_questions_for_repository(repository, request.user)
    except QuestionGenerationError as exc:
        question_set.status = QuestionSet.Status.FAILED
        question_set.error_message = str(exc)
        question_set.save(update_fields=("status", "error_message"))
        return redirect("projects:repository_detail", repository_id=repository.pk)

    with transaction.atomic():
        question_set.questions.all().delete()
        FreeResponseQuestion.objects.bulk_create(
            [
                FreeResponseQuestion(
                    question_set=question_set,
                    position=position,
                    prompt=question["prompt"],
                    focus_area=question["focus_area"][:120],
                    reference_answer=question["reference_answer"],
                    source_files=question["source_files"],
                )
                for position, question in enumerate(generated.questions, start=1)
            ]
        )
        question_set.status = QuestionSet.Status.COMPLETE
        question_set.model_name = generated.model_name
        question_set.response_id = generated.response_id
        question_set.error_message = ""
        question_set.completed_at = timezone.now()
        question_set.save(
            update_fields=(
                "status",
                "model_name",
                "response_id",
                "error_message",
                "completed_at",
            )
        )

    messages.success(request, "Five free-response questions are ready.")
    return redirect("projects:repository_detail", repository_id=repository.pk)


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    """End the current authenticated session."""
    auth_logout(request)
    return redirect("projects:home")


def health(request: HttpRequest) -> JsonResponse:
    """Provide a lightweight readiness check for local development."""
    return JsonResponse({"status": "ok", "service": "vivarepo"})
