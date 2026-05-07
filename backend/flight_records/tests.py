from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from aircraft.models import Aircraft
from pilots.models import Pilot

from .models import FlightAnalysis, FlightRecord
from .services import append_fukin, finalize_flight_record, generate_pdf_asset

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

    def test_generate_pdf_includes_3d_altitude_profile_when_analysis_has_profile(self):
        FlightAnalysis.objects.create(
            flight_record=self.record,
            max_altitude_m=30,
            max_speed_mps=8,
            max_distance_m=120,
            summary_json={
                "altitude_profile": [
                    {"x_m": 0, "y_m": 0, "relative_altitude_m": 0, "altitude_m": 10},
                    {"x_m": 35, "y_m": 8, "relative_altitude_m": 18, "altitude_m": 28},
                    {"x_m": 80, "y_m": 30, "relative_altitude_m": 12, "altitude_m": 22},
                ],
                "waypoints": [
                    {
                        "seq": 2,
                        "x_m": 35,
                        "y_m": 8,
                        "relative_altitude_m": 20,
                        "altitude_m": 30,
                    },
                ],
            },
        )

        asset = generate_pdf_asset(self.record)

        self.assertGreater(asset.file.size, 0)
        self.assertTrue(asset.file.name.endswith(".pdf"))

# Create your tests here.
