from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from aircraft.models import Aircraft
from pilots.models import Pilot

from .models import FlightAnalysis, FlightRecord
from .services import _summarize_analysis_messages, append_fukin, finalize_flight_record, generate_pdf_asset

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
                        "lat": 36.2864681,
                        "lng": 136.3556962,
                        "x_m": 35,
                        "y_m": 8,
                        "relative_altitude_m": 20,
                        "altitude_m": 30,
                    },
                    {
                        "seq": 3,
                        "lat": 36.2867681,
                        "lng": 136.3560962,
                        "x_m": 75,
                        "y_m": 28,
                        "relative_altitude_m": 18,
                        "altitude_m": 28,
                    },
                ],
            },
        )

        asset = generate_pdf_asset(self.record)

        self.assertGreater(asset.file.size, 0)
        self.assertTrue(asset.file.name.endswith(".pdf"))
        with asset.file.open("rb") as pdf_file:
            content = pdf_file.read()
        media_box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", content)
        self.assertIsNotNone(media_box)
        width = float(media_box.group(1))
        height = float(media_box.group(2))
        self.assertGreater(width, height)

    def test_analysis_summary_messages_are_human_readable(self):
        messages = _summarize_analysis_messages(
            ["最低電圧が低めです: min=12.60V"],
            [
                "Arming motors",
                "ArduCopter V4.7.0-dev (6a6d1fec)",
                "1238857f220d48609cf8b3d9d9c6a936",
                "RC Protocol: UDP",
                "EKF3 IMU0 MAG0 in-flight yaw alignment complete",
                "Mission: 1 WP",
                "Reached command #1",
                "Mission: 2 WP",
                "Reached command #2",
                "Mission: 3 WP",
            ],
        )

        joined = "\n".join(messages)
        self.assertIn("バッテリー最低電圧が12.60Vまで低下しました。", joined)
        self.assertIn("モーターがアームされ、飛行開始準備に入りました。", joined)
        self.assertIn("機体ソフトウェアは ArduCopter V4.7.0-dev です。", joined)
        self.assertIn("操縦入力は UDP 接続で記録されています。", joined)
        self.assertIn("方位センサーと姿勢推定の調整が完了しました。", joined)
        self.assertIn("ウェイポイント1〜3の飛行指示が記録されています。", joined)
        self.assertIn("ウェイポイント1〜2への到達が記録されています。", joined)
        self.assertNotIn("Arming motors", joined)
        self.assertNotIn("1238857f220d48609cf8b3d9d9c6a936", joined)

# Create your tests here.
