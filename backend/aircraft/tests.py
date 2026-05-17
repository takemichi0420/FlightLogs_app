from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Aircraft

User = get_user_model()


class AircraftApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", email="owner@example.com", password="secret123")
        self.client.force_authenticate(self.user)

    def test_certified_aircraft_requires_remote_id(self):
        response = self.client.post(
            "/api/aircraft/",
            {
                "name": "Certified",
                "model": "Quad",
                "serial_number": "SN-001",
                "registration_number": "JU-001A",
                "is_certified": True,
                "remote_id": "",
                "initial_total_flight_seconds": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("remote_id", response.data)

    def test_uncertified_aircraft_clears_remote_id(self):
        response = self.client.post(
            "/api/aircraft/",
            {
                "name": "Uncertified",
                "model": "Quad",
                "serial_number": "SN-002",
                "registration_number": "JU-002A",
                "is_certified": False,
                "remote_id": "RID-001",
                "initial_total_flight_seconds": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        aircraft = Aircraft.objects.get(pk=response.data["id"])
        self.assertFalse(aircraft.is_certified)
        self.assertEqual(aircraft.remote_id, "")
