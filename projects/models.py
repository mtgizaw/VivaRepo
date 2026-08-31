"""Persistent project records owned by VivaRepo users."""

from django.conf import settings
from django.db import models


class Repository(models.Model):
    """A repository archive uploaded by an authenticated user."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=500)
    archive = models.FileField(
        upload_to="repository_archives/%Y/%m/",
        max_length=255,
    )
    original_filename = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField()
    source_context = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="repositories",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at", "-pk")

    def __str__(self) -> str:
        return self.name
