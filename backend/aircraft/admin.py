from __future__ import annotations

from django.contrib import admin

from .models import Aircraft


@admin.register(Aircraft)
class AircraftAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "model", "serial_number", "registration_number", "owner"]
    search_fields = ["name", "model", "serial_number", "registration_number"]

# Register your models here.
