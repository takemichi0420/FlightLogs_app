from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class FlightRecord(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        ANALYZING = "analyzing", "Analyzing"
        ANALYSIS_FAILED = "analysis_failed", "Analysis Failed"
        DRAFT = "draft", "Draft"
        FINALIZED = "finalized", "Finalized"

    class DiagnosticGrade(models.TextChoices):
        NORMAL = "normal", "Normal"
        WARNING = "warning", "Warning"
        DANGER = "danger", "Danger"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="flight_records")
    aircraft = models.ForeignKey("aircraft.Aircraft", on_delete=models.SET_NULL, related_name="flight_records", blank=True, null=True)
    pilot = models.ForeignKey("pilots.Pilot", on_delete=models.SET_NULL, related_name="flight_records", blank=True, null=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.UPLOADED)
    source_file = models.FileField(upload_to="logs/%Y/%m/%d/")
    source_original_name = models.CharField(max_length=255, blank=True)
    source_log_type = models.CharField(max_length=16, blank=True)
    vehicle_type = models.CharField(max_length=128, default="ArduPilot Copter")
    flight_date = models.DateField(blank=True, null=True)
    takeoff_at_utc = models.DateTimeField(blank=True, null=True)
    landing_at_utc = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(blank=True, null=True)
    takeoff_lat = models.FloatField(blank=True, null=True)
    takeoff_lng = models.FloatField(blank=True, null=True)
    takeoff_address = models.CharField(max_length=512, blank=True)
    landing_lat = models.FloatField(blank=True, null=True)
    landing_lng = models.FloatField(blank=True, null=True)
    landing_address = models.CharField(max_length=512, blank=True)
    purpose = models.TextField(blank=True)
    special_flight_types = models.TextField(blank=True)
    route_summary = models.TextField(blank=True)
    official_weather = models.CharField(max_length=255, blank=True)
    official_temperature_c = models.FloatField(blank=True, null=True)
    official_wind_speed_mps = models.FloatField(blank=True, null=True)
    reference_weather = models.CharField(max_length=255, blank=True)
    reference_temperature_c = models.FloatField(blank=True, null=True)
    reference_wind_speed_mps = models.FloatField(blank=True, null=True)
    reference_station_name = models.CharField(max_length=255, blank=True)
    reference_station_distance_km = models.FloatField(blank=True, null=True)
    reference_observed_at = models.DateTimeField(blank=True, null=True)
    reference_source = models.CharField(max_length=255, blank=True)
    safety_notes = models.TextField(blank=True)
    article_notes = models.TextField(blank=True)
    pilot_signature = models.CharField(max_length=255, blank=True)
    diagnostic_grade = models.CharField(max_length=16, choices=DiagnosticGrade.choices, blank=True)
    review_required = models.BooleanField(default=False)
    analysis_error = models.TextField(blank=True)
    aircraft_snapshot = models.JSONField(default=dict, blank=True)
    pilot_snapshot = models.JSONField(default=dict, blank=True)
    finalized_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"FlightRecord #{self.pk}"


class AnalysisJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flight_record = models.OneToOneField(FlightRecord, on_delete=models.CASCADE, related_name="analysis_job")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]


class FlightAnalysis(models.Model):
    flight_record = models.OneToOneField(FlightRecord, on_delete=models.CASCADE, related_name="analysis")
    arm_at_utc = models.DateTimeField(blank=True, null=True)
    disarm_at_utc = models.DateTimeField(blank=True, null=True)
    takeoff_detected_by = models.CharField(max_length=64, blank=True)
    landing_detected_by = models.CharField(max_length=64, blank=True)
    max_altitude_m = models.FloatField(blank=True, null=True)
    max_speed_mps = models.FloatField(blank=True, null=True)
    max_distance_m = models.FloatField(blank=True, null=True)
    battery_start_voltage = models.FloatField(blank=True, null=True)
    battery_end_voltage = models.FloatField(blank=True, null=True)
    battery_min_voltage = models.FloatField(blank=True, null=True)
    battery_max_current = models.FloatField(blank=True, null=True)
    battery_consumed_mah = models.FloatField(blank=True, null=True)
    gps_min_satellites = models.IntegerField(blank=True, null=True)
    gps_max_hdop = models.FloatField(blank=True, null=True)
    ekf_summary = models.TextField(blank=True)
    vibration_summary = models.TextField(blank=True)
    failsafe_events = models.JSONField(default=list, blank=True)
    warning_messages = models.JSONField(default=list, blank=True)
    error_messages = models.JSONField(default=list, blank=True)
    summary_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FlightModeSpan(models.Model):
    flight_record = models.ForeignKey(FlightRecord, on_delete=models.CASCADE, related_name="mode_spans")
    mode_name = models.CharField(max_length=128)
    start_at_utc = models.DateTimeField(blank=True, null=True)
    end_at_utc = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ["start_at_utc", "id"]


class FlightTimeLedger(models.Model):
    aircraft = models.ForeignKey("aircraft.Aircraft", on_delete=models.CASCADE, related_name="flight_time_entries")
    flight_record = models.OneToOneField(FlightRecord, on_delete=models.CASCADE, related_name="flight_time_ledger")
    added_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class GeneratedAsset(models.Model):
    class AssetType(models.TextChoices):
        PDF = "pdf", "PDF"

    flight_record = models.ForeignKey(FlightRecord, on_delete=models.CASCADE, related_name="generated_assets")
    asset_type = models.CharField(max_length=32, choices=AssetType.choices)
    file = models.FileField(upload_to="reports/%Y/%m/%d/")
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at", "-id"]

# Create your models here.
