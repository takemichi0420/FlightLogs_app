from __future__ import annotations

from rest_framework import serializers

from .models import Pilot


class PilotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pilot
        fields = [
            "id",
            "name",
            "license_number",
            "organization",
            "signature_image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
