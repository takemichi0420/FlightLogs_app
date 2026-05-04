from __future__ import annotations

from django.contrib import admin

from .models import AnalysisJob, FlightAnalysis, FlightModeSpan, FlightRecord, FlightTimeLedger, GeneratedAsset


@admin.register(FlightRecord)
class FlightRecordAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "flight_date", "owner", "aircraft", "pilot", "diagnostic_grade"]
    list_filter = ["status", "diagnostic_grade", "review_required"]
    search_fields = ["source_original_name", "takeoff_address", "landing_address"]


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = ["id", "flight_record", "status", "created_at", "finished_at"]


@admin.register(FlightAnalysis)
class FlightAnalysisAdmin(admin.ModelAdmin):
    list_display = ["flight_record", "max_altitude_m", "max_speed_mps", "gps_min_satellites"]


@admin.register(FlightModeSpan)
class FlightModeSpanAdmin(admin.ModelAdmin):
    list_display = ["flight_record", "mode_name", "start_at_utc", "end_at_utc", "duration_seconds"]


@admin.register(FlightTimeLedger)
class FlightTimeLedgerAdmin(admin.ModelAdmin):
    list_display = ["flight_record", "aircraft", "added_seconds", "created_at"]


@admin.register(GeneratedAsset)
class GeneratedAssetAdmin(admin.ModelAdmin):
    list_display = ["id", "flight_record", "asset_type", "generated_at"]

# Register your models here.
