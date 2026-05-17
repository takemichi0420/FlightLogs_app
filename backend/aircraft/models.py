from __future__ import annotations

from django.conf import settings
from django.db import models


class Aircraft(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="aircraft")
    registration_number = models.CharField(max_length=128, blank=True)
    is_certified = models.BooleanField(default=False)
    remote_id = models.CharField(max_length=128, blank=True)
    model = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    initial_total_flight_seconds = models.PositiveIntegerField(default=0)
    current_total_flight_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name

# Create your models here.
