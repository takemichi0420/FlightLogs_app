from __future__ import annotations

from rest_framework import permissions, viewsets

from .models import Pilot
from .serializers import PilotSerializer


class PilotViewSet(viewsets.ModelViewSet):
    serializer_class = PilotSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "license_number", "organization"]
    ordering_fields = ["name", "created_at", "updated_at"]

    def get_queryset(self):
        return Pilot.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

# Create your views here.
