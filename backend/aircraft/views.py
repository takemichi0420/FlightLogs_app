from __future__ import annotations

from rest_framework import permissions, viewsets

from .models import Aircraft
from .serializers import AircraftSerializer


class AircraftViewSet(viewsets.ModelViewSet):
    serializer_class = AircraftSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "model", "serial_number", "registration_number"]
    ordering_fields = ["name", "created_at", "updated_at"]

    def get_queryset(self):
        return Aircraft.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

# Create your views here.
