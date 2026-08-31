"""Tests for authenticated repository intake."""

from io import BytesIO
import shutil
import tempfile
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from projects.models import Repository


User = get_user_model()


def repository_zip(filename: str = "project.zip") -> SimpleUploadedFile:
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr("project/README.md", "# Example")
        archive.writestr("project/app.py", "print('hello')")
    return SimpleUploadedFile(filename, content.getvalue(), "application/zip")


class RepositoryUploadTests(TestCase):
    password = "StrongPass-2026!"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.settings_override.disable()
        shutil.rmtree(cls.media_root)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="martha",
            email="martha@example.com",
            password=self.password,
        )

    def test_anonymous_user_is_redirected_to_login_with_return_url(self):
        upload_url = reverse("projects:upload_repository")

        response = self.client.get(upload_url)

        self.assertRedirects(
            response,
            f'{reverse("projects:login")}?next={upload_url}',
        )

    def test_login_returns_user_to_the_upload_page(self):
        upload_url = reverse("projects:upload_repository")

        response = self.client.post(
            reverse("projects:login"),
            {
                "email": self.user.email,
                "password": self.password,
                "next": upload_url,
            },
        )

        self.assertRedirects(response, upload_url)

    def test_user_can_upload_a_repository_zip(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("projects:upload_repository"),
            {
                "name": "Habit tracker",
                "description": "A tiny learning project.",
                "archive": repository_zip(),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        repository = Repository.objects.get()
        self.assertEqual(repository.uploaded_by, self.user)
        self.assertEqual(repository.original_filename, "project.zip")
        self.assertGreater(repository.size_bytes, 0)
        self.assertIn("project/app.py", repository.source_context)
        self.assertContains(response, "was uploaded and is ready for analysis")
        self.assertContains(response, "Habit tracker")

    def test_non_zip_file_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("projects:upload_repository"),
            {
                "name": "Not a repository",
                "archive": SimpleUploadedFile("notes.txt", b"hello", "text/plain"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a repository as a .zip file.")
        self.assertFalse(Repository.objects.exists())

    def test_page_only_lists_repositories_owned_by_current_user(self):
        other = User.objects.create_user(username="other", password=self.password)
        Repository.objects.create(
            name="Someone else's project",
            archive=repository_zip("other.zip"),
            original_filename="other.zip",
            size_bytes=100,
            uploaded_by=other,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("projects:upload_repository"))

        self.assertNotContains(response, "Someone else&#x27;s project")
