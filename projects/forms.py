"""Forms for VivaRepo authentication and repository intake."""

from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import AbstractBaseUser

from ai.repository_questions import QuestionGenerationError, build_archive_context

from .models import Repository


User = get_user_model()

MAX_ARCHIVE_SIZE = 50 * 1024 * 1024
MAX_UNCOMPRESSED_SIZE = 500 * 1024 * 1024
MAX_ARCHIVE_FILES = 20_000


def validate_repository_archive(archive) -> str:
    """Validate a ZIP and return the durable, bounded source context."""
    if not archive.name.lower().endswith(".zip"):
        raise forms.ValidationError("Upload a repository as a .zip file.")
    if archive.size > MAX_ARCHIVE_SIZE:
        raise forms.ValidationError("The ZIP file must be 50 MB or smaller.")

    try:
        archive.seek(0)
        with ZipFile(archive) as zip_file:
            files = [entry for entry in zip_file.infolist() if not entry.is_dir()]
            if not files:
                raise forms.ValidationError("The ZIP file does not contain any files.")
            if len(files) > MAX_ARCHIVE_FILES:
                raise forms.ValidationError("The ZIP file contains too many files.")
            if sum(entry.file_size for entry in files) > MAX_UNCOMPRESSED_SIZE:
                raise forms.ValidationError(
                    "The repository is too large after decompression."
                )
            for entry in files:
                path = PurePosixPath(entry.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts:
                    raise forms.ValidationError(
                        "The ZIP file contains an unsafe file path."
                    )
    except (BadZipFile, OSError):
        raise forms.ValidationError("The selected file is not a valid ZIP archive.")
    finally:
        archive.seek(0)

    try:
        return build_archive_context(archive)
    except QuestionGenerationError as exc:
        raise forms.ValidationError(str(exc)) from exc


class SignupForm(UserCreationForm):
    """Create a local user while requiring a unique email address."""

    email = forms.EmailField()
    terms = forms.BooleanField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self) -> str:
        """Prevent ambiguous email-based login identifiers."""
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit: bool = True) -> AbstractBaseUser:
        """Store the normalized email and Django-hashed password."""
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class EmailLoginForm(forms.Form):
    """Authenticate a local user by email and password."""

    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    remember_me = forms.BooleanField(required=False)

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user_cache = None

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if not email or not password:
            return cleaned_data

        matching_users = list(
            User.objects.filter(email__iexact=email).order_by("pk")[:2]
        )
        if len(matching_users) == 1:
            user = matching_users[0]
            self.user_cache = authenticate(
                self.request,
                username=user.get_username(),
                password=password,
            )

        if self.user_cache is None:
            raise forms.ValidationError("Email or password is incorrect.")

        if not self.user_cache.is_active:
            raise forms.ValidationError("This account is inactive.")

        return cleaned_data

    def get_user(self):
        """Return the authenticated user after validation."""
        return self.user_cache


class RepositoryUploadForm(forms.ModelForm):
    """Validate repository ZIP archives before they enter storage."""

    class Meta:
        model = Repository
        fields = ("name", "description", "archive")

    def clean_archive(self):
        archive = self.cleaned_data["archive"]
        self.repository_context = validate_repository_archive(archive)
        return archive


class RepositoryArchiveReplacementForm(forms.Form):
    """Replace an unavailable archive while preserving the repository record."""

    archive = forms.FileField()

    def clean_archive(self):
        archive = self.cleaned_data["archive"]
        self.repository_context = validate_repository_archive(archive)
        return archive


class AssessmentAnswerForm(forms.Form):
    """Require one substantive free-response answer for every question."""

    def __init__(self, questions, *args, initial_answers=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = list(questions)
        initial_answers = initial_answers or {}
        for question in self.questions:
            self.fields[f"question_{question.pk}"] = forms.CharField(
                min_length=10,
                max_length=5_000,
                label=f"Answer to question {question.position}",
                initial=initial_answers.get(question.pk, ""),
                error_messages={
                    "required": "Answer this question before submitting.",
                    "min_length": "Add a little more detail before submitting.",
                },
                widget=forms.Textarea(
                    attrs={
                        "rows": 6,
                        "placeholder": "Explain your answer and reasoning…",
                    }
                ),
            )

    def answers_by_question_id(self) -> dict[int, str]:
        """Return validated answers keyed by their question IDs."""
        return {
            question.pk: self.cleaned_data[f"question_{question.pk}"].strip()
            for question in self.questions
        }
