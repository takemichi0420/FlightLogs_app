from __future__ import annotations

from django.conf import settings
from django.db import models


class Pilot(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pilots")
    name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=255, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    signature_image = models.ImageField(upload_to="signatures/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name

# Create your models here.
