from __future__ import annotations

from rest_framework import serializers

from .models import Aircraft


class AircraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aircraft
        fields = [
            "id",
            "registration_number",
            "is_certified",
            "remote_id",
            "model",
            "serial_number",
            "name",
            "initial_total_flight_seconds",
            "current_total_flight_seconds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["current_total_flight_seconds", "created_at", "updated_at"]

    def validate(self, attrs):
        is_certified = attrs.get("is_certified", getattr(self.instance, "is_certified", False))
        remote_id = attrs.get("remote_id", getattr(self.instance, "remote_id", ""))
        if is_certified and not str(remote_id).strip():
            raise serializers.ValidationError({"remote_id": "機体認証済みの場合はリモートIDを入力してください。"})
        if not is_certified:
            attrs["remote_id"] = ""
        return attrs
