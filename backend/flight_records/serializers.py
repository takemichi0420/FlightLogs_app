from __future__ import annotations

from rest_framework import serializers

from aircraft.models import Aircraft
from pilots.models import Pilot

from .models import AnalysisJob, FlightAnalysis, FlightModeSpan, FlightRecord, GeneratedAsset


class GeneratedAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedAsset
        fields = ["id", "asset_type", "file", "generated_at"]


class FlightModeSpanSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightModeSpan
        fields = ["id", "mode_name", "start_at_utc", "end_at_utc", "duration_seconds"]


class FlightAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightAnalysis
        fields = [
            "arm_at_utc",
            "disarm_at_utc",
            "takeoff_detected_by",
            "landing_detected_by",
            "max_altitude_m",
            "max_speed_mps",
            "max_distance_m",
            "battery_start_voltage",
            "battery_end_voltage",
            "battery_min_voltage",
            "battery_max_current",
            "battery_consumed_mah",
            "gps_min_satellites",
            "gps_max_hdop",
            "ekf_summary",
            "vibration_summary",
            "failsafe_events",
            "warning_messages",
            "error_messages",
            "summary_json",
        ]


class AnalysisJobSerializer(serializers.ModelSerializer):
    flight_record_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = AnalysisJob
        fields = ["id", "flight_record_id", "status", "error_message", "created_at", "started_at", "finished_at"]


class FlightRecordSerializer(serializers.ModelSerializer):
    analysis = FlightAnalysisSerializer(read_only=True)
    mode_spans = FlightModeSpanSerializer(many=True, read_only=True)
    generated_assets = GeneratedAssetSerializer(many=True, read_only=True)
    analysis_job = AnalysisJobSerializer(read_only=True)

    class Meta:
        model = FlightRecord
        fields = [
            "id",
            "aircraft",
            "pilot",
            "status",
            "source_file",
            "source_original_name",
            "source_log_type",
            "vehicle_type",
            "flight_date",
            "takeoff_at_utc",
            "landing_at_utc",
            "duration_seconds",
            "takeoff_lat",
            "takeoff_lng",
            "takeoff_address",
            "landing_lat",
            "landing_lng",
            "landing_address",
            "purpose",
            "special_flight_types",
            "route_summary",
            "official_weather",
            "official_temperature_c",
            "official_wind_speed_mps",
            "reference_weather",
            "reference_temperature_c",
            "reference_wind_speed_mps",
            "reference_station_name",
            "reference_station_distance_km",
            "reference_observed_at",
            "reference_source",
            "safety_notes",
            "article_notes",
            "diagnostic_grade",
            "review_required",
            "analysis_error",
            "aircraft_snapshot",
            "pilot_snapshot",
            "finalized_at",
            "created_at",
            "updated_at",
            "analysis",
            "mode_spans",
            "generated_assets",
            "analysis_job",
        ]
        read_only_fields = [
            "status",
            "source_file",
            "source_original_name",
            "source_log_type",
            "flight_date",
            "takeoff_at_utc",
            "landing_at_utc",
            "duration_seconds",
            "takeoff_lat",
            "takeoff_lng",
            "takeoff_address",
            "landing_lat",
            "landing_lng",
            "landing_address",
            "reference_weather",
            "reference_temperature_c",
            "reference_wind_speed_mps",
            "reference_station_name",
            "reference_station_distance_km",
            "reference_observed_at",
            "reference_source",
            "diagnostic_grade",
            "review_required",
            "analysis_error",
            "aircraft_snapshot",
            "pilot_snapshot",
            "finalized_at",
            "created_at",
            "updated_at",
            "analysis",
            "mode_spans",
            "generated_assets",
            "analysis_job",
        ]

    def validate_aircraft(self, value: Aircraft):
        request = self.context["request"]
        if value.owner_id != request.user.id:
            raise serializers.ValidationError("自分の機体のみ選択できます。")
        return value

    def validate_pilot(self, value: Pilot):
        request = self.context["request"]
        if value.owner_id != request.user.id:
            raise serializers.ValidationError("自分の操縦者のみ選択できます。")
        return value


class LogUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    aircraft_id = serializers.IntegerField(required=False)
    pilot_id = serializers.IntegerField(required=False)
    vehicle_type = serializers.CharField(required=False, default="ArduPilot Copter")

    def validate_file(self, value):
        suffix = value.name.lower().rsplit(".", 1)[-1] if "." in value.name else ""
        if suffix not in {"bin", "log"}:
            raise serializers.ValidationError("対応しているログ形式は .bin と .log のみです。")
        return value


class MavlinkConnectionSerializer(serializers.Serializer):
    connection = serializers.CharField(default="udp:127.0.0.1:14550", max_length=255)
    baud = serializers.IntegerField(required=False, default=115200, min_value=1200, max_value=3000000)
    timeout_s = serializers.FloatField(required=False, default=10, min_value=1, max_value=120)


class MavlinkLogImportSerializer(MavlinkConnectionSerializer):
    log_id = serializers.IntegerField(required=False, min_value=0)
    aircraft_id = serializers.IntegerField(required=False)
    pilot_id = serializers.IntegerField(required=False)
    vehicle_type = serializers.CharField(required=False, default="ArduPilot Copter")
