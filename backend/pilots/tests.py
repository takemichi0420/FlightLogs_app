from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Pilot

User = get_user_model()


class PilotApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", email="owner@example.com", password="secret123")
        self.other_user = User.objects.create_user(username="other", email="other@example.com", password="secret123")
        self.client.force_authenticate(self.user)

    def test_authenticated_user_can_create_pilot(self):
        response = self.client.post(
            "/api/pilots/",
            {
                "name": "操縦者A",
                "license_number": "LIC-001",
                "organization": "運航部",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pilot = Pilot.objects.get(pk=response.data["id"])
        self.assertEqual(pilot.owner, self.user)
        self.assertEqual(pilot.name, "操縦者A")
        self.assertEqual(pilot.license_number, "LIC-001")
        self.assertEqual(pilot.organization, "運航部")

    def test_pilot_list_is_limited_to_owner(self):
        own_pilot = Pilot.objects.create(owner=self.user, name="自分の操縦者")
        Pilot.objects.create(owner=self.other_user, name="他人の操縦者")

        response = self.client.get("/api/pilots/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], own_pilot.id)
