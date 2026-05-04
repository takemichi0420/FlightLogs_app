from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from aircraft.models import Aircraft
from pilots.models import Pilot

from .models import FlightRecord
from .services import append_fukin, finalize_flight_record

User = get_user_model()


class FlightRecordServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pilot", email="pilot@example.com", password="secret123")
        self.aircraft = Aircraft.objects.create(
            owner=self.user,
            name="Test Craft",
            model="Quad",
            serial_number="SN-001",
            registration_number="JU-001A",
            initial_total_flight_seconds=0,
            current_total_flight_seconds=120,
        )
        self.pilot = Pilot.objects.create(owner=self.user, name="Operator A")
        self.record = FlightRecord.objects.create(
            owner=self.user,
            aircraft=self.aircraft,
            pilot=self.pilot,
            status=FlightRecord.Status.DRAFT,
            source_file=SimpleUploadedFile("flight.bin", b"test"),
            source_original_name="flight.bin",
            source_log_type="bin",
            official_weather="晴れ",
            official_temperature_c=22.5,
            official_wind_speed_mps=2.1,
            duration_seconds=300,
        )

    def test_append_fukin_is_idempotent(self):
        self.assertEqual(append_fukin("東京都江東区"), "東京都江東区付近")
        self.assertEqual(append_fukin("東京都江東区付近"), "東京都江東区付近")

    def test_finalize_does_not_double_add_total_flight_time(self):
        finalize_flight_record(self.record)
        self.aircraft.refresh_from_db()
        self.assertEqual(self.aircraft.current_total_flight_seconds, 420)

        finalize_flight_record(self.record)
        self.aircraft.refresh_from_db()
        self.assertEqual(self.aircraft.current_total_flight_seconds, 420)

# Create your tests here.
