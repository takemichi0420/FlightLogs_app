from __future__ import annotations

from django.contrib import admin

from .models import Aircraft


@admin.register(Aircraft)
class AircraftAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "model", "serial_number", "registration_number", "is_certified", "remote_id", "owner"]
    list_filter = ["is_certified"]
    search_fields = ["name", "model", "serial_number", "registration_number", "remote_id"]

# Register your models here.
