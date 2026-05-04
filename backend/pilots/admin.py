from __future__ import annotations

from django.contrib import admin

from .models import Pilot


@admin.register(Pilot)
class PilotAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "license_number", "owner"]
    search_fields = ["name", "license_number", "organization"]

# Register your models here.
