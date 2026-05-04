from __future__ import annotations

from rest_framework import serializers

from .models import Aircraft


class AircraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aircraft
        fields = [
            "id",
            "registration_number",
            "model",
            "serial_number",
            "name",
            "initial_total_flight_seconds",
            "current_total_flight_seconds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["current_total_flight_seconds", "created_at", "updated_at"]
