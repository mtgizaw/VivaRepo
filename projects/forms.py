"""Forms for local VivaRepo account registration and authentication."""

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import AbstractBaseUser


User = get_user_model()


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
