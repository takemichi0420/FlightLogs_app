from __future__ import annotations

import io
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F
from django.utils import timezone as dj_timezone
from pymavlink import DFReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import FlightAnalysis, FlightModeSpan, FlightRecord, FlightTimeLedger, GeneratedAsset

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(converted):
        return None
    return converted


def _format_meters(value: Any) -> str:
    converted = _to_float(value)
    if converted is None:
        return "-"
    rounded = round(converted, 1)
    if rounded.is_integer():
        return f"{rounded:.0f}m"
    return f"{rounded:.1f}m"


class AltitudeProfile3DChart(Flowable):
    def __init__(self, profile: list[dict[str, Any]], waypoints: list[dict[str, Any]]) -> None:
        super().__init__()
        self.profile = self._clean_profile(profile)
        self.waypoints = self._clean_waypoints(waypoints)
        self.width = 0
        self.height = 82 * mm

    @staticmethod
    def _clean_profile(profile: list[dict[str, Any]]) -> list[dict[str, float]]:
        points: list[dict[str, float]] = []
        for item in profile:
            x_m = _to_float(item.get("x_m"))
            y_m = _to_float(item.get("y_m"))
            altitude_m = _to_float(item.get("relative_altitude_m"))
            if x_m is None or y_m is None or altitude_m is None:
                continue
            points.append({"x_m": x_m, "y_m": y_m, "relative_altitude_m": max(altitude_m, 0.0)})
        return points

    @staticmethod
    def _clean_waypoints(waypoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        for item in waypoints:
            x_m = _to_float(item.get("x_m"))
            y_m = _to_float(item.get("y_m"))
            relative_altitude_m = _to_float(item.get("relative_altitude_m"))
            if x_m is None or y_m is None or relative_altitude_m is None:
                continue
            points.append(
                {
                    "seq": item.get("seq"),
                    "x_m": x_m,
                    "y_m": y_m,
                    "relative_altitude_m": max(relative_altitude_m, 0.0),
                    "altitude_m": item.get("altitude_m"),
                }
            )
        return points

    @property
    def has_data(self) -> bool:
        return len(self.profile) >= 2

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        del avail_height
        self.width = min(avail_width, 178 * mm)
        return self.width, self.height

    def _projector(self, left: float, bottom: float, area_width: float, area_height: float):
        def raw_project(x: float, y: float, z: float) -> tuple[float, float]:
            return x + 0.62 * y, 1.34 * z + 0.38 * y

        corners = [
            raw_project(x, y, z)
            for x in (-1.0, 1.0)
            for y in (-1.0, 1.0)
            for z in (0.0, 1.0)
        ]
        min_x = min(point[0] for point in corners)
        max_x = max(point[0] for point in corners)
        min_y = min(point[1] for point in corners)
        max_y = max(point[1] for point in corners)
        raw_width = max_x - min_x
        raw_height = max_y - min_y
        scale = min(area_width / raw_width, area_height / raw_height)
        offset_x = left + (area_width - raw_width * scale) / 2 - min_x * scale
        offset_y = bottom + (area_height - raw_height * scale) / 2 - min_y * scale

        def project(x: float, y: float, z: float) -> tuple[float, float]:
            raw_x, raw_y = raw_project(x, y, z)
            return offset_x + raw_x * scale, offset_y + raw_y * scale

        return project

    def _normalizers(self):
        points = [*self.profile, *self.waypoints]
        x_values = [point["x_m"] for point in points]
        y_values = [point["y_m"] for point in points]
        altitude_values = [point["relative_altitude_m"] for point in points]
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2
        horizontal_span = max(x_max - x_min, y_max - y_min, 1.0)
        altitude_span = max(max(altitude_values), 1.0)

        def normalize(point: dict[str, Any], ground: bool = False) -> tuple[float, float, float]:
            x = ((point["x_m"] - x_center) / horizontal_span) * 2
            y = ((point["y_m"] - y_center) / horizontal_span) * 2
            z = 0.0 if ground else min(max(point["relative_altitude_m"] / altitude_span, 0.0), 1.0)
            return x, y, z

        return normalize

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        try:
            self._draw_chart(canvas)
        finally:
            canvas.restoreState()

    def _draw_chart(self, canvas) -> None:
        canvas.setFillColor(colors.HexColor("#f8fbfd"))
        canvas.setStrokeColor(colors.HexColor("#d7e3ec"))
        canvas.roundRect(0, 0, self.width, self.height, 8, fill=1, stroke=1)

        canvas.setFont("HeiseiKakuGo-W5", 11)
        canvas.setFillColor(colors.HexColor("#0f2535"))
        canvas.drawString(8 * mm, self.height - 10 * mm, "3D高度プロファイル")
        canvas.setFont("HeiseiKakuGo-W5", 7.5)
        canvas.setFillColor(colors.HexColor("#587084"))
        canvas.drawString(8 * mm, self.height - 15 * mm, "Z=高度 / X・Y=水平位置 / 橙=waypoint")

        if not self.has_data:
            canvas.setFont("HeiseiKakuGo-W5", 9)
            canvas.setFillColor(colors.HexColor("#64748b"))
            canvas.drawCentredString(self.width / 2, self.height / 2, "高度時系列データがありません。")
            return

        left = 8 * mm
        bottom = 8 * mm
        area_width = self.width - 16 * mm
        area_height = self.height - 28 * mm
        project = self._projector(left, bottom, area_width, area_height)
        normalize = self._normalizers()

        def projected(point: dict[str, Any], ground: bool = False) -> tuple[float, float]:
            return project(*normalize(point, ground=ground))

        def draw_line(points: list[tuple[float, float]], color: colors.Color, width: float) -> None:
            if len(points) < 2:
                return
            canvas.setStrokeColor(color)
            canvas.setLineWidth(width)
            path = canvas.beginPath()
            path.moveTo(points[0][0], points[0][1])
            for x, y in points[1:]:
                path.lineTo(x, y)
            canvas.drawPath(path, stroke=1, fill=0)

        box_edges = [
            ((-1, -1, 0), (1, -1, 0)),
            ((1, -1, 0), (1, 1, 0)),
            ((1, 1, 0), (-1, 1, 0)),
            ((-1, 1, 0), (-1, -1, 0)),
            ((-1, -1, 1), (1, -1, 1)),
            ((1, -1, 1), (1, 1, 1)),
            ((1, 1, 1), (-1, 1, 1)),
            ((-1, 1, 1), (-1, -1, 1)),
            ((-1, -1, 0), (-1, -1, 1)),
            ((1, -1, 0), (1, -1, 1)),
            ((1, 1, 0), (1, 1, 1)),
            ((-1, 1, 0), (-1, 1, 1)),
        ]
        canvas.setStrokeColor(colors.HexColor("#cbd5df"))
        canvas.setLineWidth(0.45)
        for start, end in box_edges:
            x1, y1 = project(*start)
            x2, y2 = project(*end)
            canvas.line(x1, y1, x2, y2)

        canvas.setStrokeColor(colors.HexColor("#dbe7ef"))
        canvas.setLineWidth(0.35)
        for index in range(1, 4):
            z = index / 4
            for start, end in [
                ((-1, -1, z), (1, -1, z)),
                ((-1, -1, z), (-1, 1, z)),
                ((-1, 1, 0), (1, 1, 0)),
                ((index / 2 - 1, -1, 0), (index / 2 - 1, 1, 0)),
            ]:
                x1, y1 = project(*start)
                x2, y2 = project(*end)
                canvas.line(x1, y1, x2, y2)

        top_points = [projected(point) for point in self.profile]
        ground_points = [projected(point, ground=True) for point in self.profile]

        canvas.setFillColor(colors.HexColor("#dcfce7"))
        if hasattr(canvas, "setFillAlpha"):
            canvas.setFillAlpha(0.55)
        for index in range(len(top_points) - 1):
            path = canvas.beginPath()
            path.moveTo(ground_points[index][0], ground_points[index][1])
            path.lineTo(top_points[index][0], top_points[index][1])
            path.lineTo(top_points[index + 1][0], top_points[index + 1][1])
            path.lineTo(ground_points[index + 1][0], ground_points[index + 1][1])
            path.close()
            canvas.drawPath(path, stroke=0, fill=1)
        if hasattr(canvas, "setFillAlpha"):
            canvas.setFillAlpha(1)

        draw_line(ground_points, colors.HexColor("#94a3b8"), 0.55)
        draw_line(top_points, colors.HexColor("#166534"), 2.1)

        canvas.setFillColor(colors.white)
        canvas.setStrokeColor(colors.HexColor("#166534"))
        canvas.setLineWidth(1.2)
        for x, y in (top_points[0], top_points[-1]):
            canvas.circle(x, y, 2.4, stroke=1, fill=1)

        waypoint_points = [projected(point) for point in self.waypoints]
        waypoint_ground_points = [projected(point, ground=True) for point in self.waypoints]
        draw_line(waypoint_points, colors.HexColor("#f97316"), 1.0)

        canvas.setFont("HeiseiKakuGo-W5", 7.2)
        for index, waypoint in enumerate(self.waypoints):
            x, y = waypoint_points[index]
            gx, gy = waypoint_ground_points[index]
            canvas.setStrokeColor(colors.HexColor("#fb923c"))
            canvas.setLineWidth(0.5)
            canvas.line(gx, gy, x, y)
            canvas.setFillColor(colors.HexColor("#f97316"))
            canvas.setStrokeColor(colors.white)
            canvas.circle(x, y, 2.8, stroke=1, fill=1)

            waypoint_seq = waypoint.get("seq")
            label_seq = index if waypoint_seq in ("", None) else waypoint_seq
            label = f"WP{label_seq} {_format_meters(waypoint.get('altitude_m'))}"
            label_width = canvas.stringWidth(label, "HeiseiKakuGo-W5", 7.2) + 4 * mm
            label_x = min(max(x + 2.5 * mm, 2 * mm), self.width - label_width - 2 * mm)
            label_y = min(max(y + 2 * mm, 2 * mm), self.height - 8 * mm)
            canvas.setFillColor(colors.white)
            canvas.setStrokeColor(colors.HexColor("#fed7aa"))
            canvas.roundRect(label_x, label_y - 1.5 * mm, label_width, 5 * mm, 2, fill=1, stroke=1)
            canvas.setFillColor(colors.HexColor("#c2410c"))
            canvas.drawString(label_x + 2 * mm, label_y, label)

        canvas.setFont("HeiseiKakuGo-W5", 8)
        canvas.setFillColor(colors.HexColor("#475569"))
        for label, point in [
            ("X", (1.08, 1.02, 0.0)),
            ("Y", (-1.1, 1.12, 0.0)),
            ("Z", (-1.1, -1.08, 1.03)),
        ]:
            x, y = project(*point)
            canvas.drawString(x, y, label)


@dataclass
class ParsedModeSpan:
    mode_name: str
    start_at_utc: datetime | None
    end_at_utc: datetime | None
    duration_seconds: int | None


@dataclass
class ParsedFlightLog:
    flight_date: date | None = None
    arm_at_utc: datetime | None = None
    disarm_at_utc: datetime | None = None
    takeoff_at_utc: datetime | None = None
    landing_at_utc: datetime | None = None
    takeoff_detected_by: str = ""
    landing_detected_by: str = ""
    duration_seconds: int | None = None
    takeoff_lat: float | None = None
    takeoff_lng: float | None = None
    landing_lat: float | None = None
    landing_lng: float | None = None
    max_altitude_m: float | None = None
    max_speed_mps: float | None = None
    max_distance_m: float | None = None
    battery_start_voltage: float | None = None
    battery_end_voltage: float | None = None
    battery_min_voltage: float | None = None
    battery_max_current: float | None = None
    battery_consumed_mah: float | None = None
    gps_min_satellites: int | None = None
    gps_max_hdop: float | None = None
    ekf_summary: str = ""
    vibration_summary: str = ""
    failsafe_events: list[str] = field(default_factory=list)
    warning_messages: list[str] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)
    summary_json: dict[str, Any] = field(default_factory=dict)
    review_required: bool = False
    diagnostic_grade: str = FlightRecord.DiagnosticGrade.NORMAL
    mode_spans: list[ParsedModeSpan] = field(default_factory=list)


def append_fukin(address: str) -> str:
    cleaned = (address or "").strip()
    if not cleaned:
        return "住所取得不可"
    if cleaned.endswith("付近"):
        return cleaned
    return f"{cleaned}付近"


def fallback_address(lat: float | None, lng: float | None) -> str:
    if lat is None or lng is None:
        return "住所取得不可"
    return append_fukin(f"緯度 {lat:.6f}, 経度 {lng:.6f}")


def reverse_geocode(lat: float | None, lng: float | None) -> str:
    if lat is None or lng is None:
        return "住所取得不可"

    base_url = os.getenv("REVERSE_GEOCODE_URL", "").strip()
    if not base_url:
        return fallback_address(lat, lng)

    try:
        response = requests.get(
            base_url,
            params={"lat": lat, "lon": lng, "format": "jsonv2"},
            timeout=5,
            headers={"User-Agent": "flight-record-app/0.1"},
        )
        response.raise_for_status()
        address = response.json().get("display_name", "")
        return append_fukin(address) if address else fallback_address(lat, lng)
    except Exception:
        logger.exception("Reverse geocoding failed")
        return fallback_address(lat, lng)


def get_weather_reference(lat: float | None, lng: float | None, observed_at: datetime | None) -> dict[str, Any]:
    del lat, lng, observed_at
    return {
        "reference_weather": "",
        "reference_temperature_c": None,
        "reference_wind_speed_mps": None,
        "reference_station_name": "",
        "reference_station_distance_km": None,
        "reference_observed_at": None,
        "reference_source": "reference_unavailable",
    }


def _safe_get(message: Any, candidates: list[str]) -> Any:
    for name in candidates:
        if hasattr(message, name):
            return getattr(message, name)
    return None


def _safe_float(message: Any, candidates: list[str]) -> float | None:
    value = _safe_get(message, candidates)
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(message: Any, candidates: list[str]) -> int | None:
    value = _safe_get(message, candidates)
    if value in ("", None):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_text(message: Any, candidates: list[str]) -> str:
    value = _safe_get(message, candidates)
    if value is None:
        return ""
    return str(value).strip()


def _normalize_coord(value: float | None, limit: float) -> float | None:
    if value is None:
        return None
    if abs(value) > limit and abs(value) > 100000:
        return value / 10000000.0
    return value


def _normalize_altitude(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) > 10000:
        return value / 100.0
    return value


def _normalize_speed(value: float | None) -> float | None:
    if value is None:
        return None
    if value > 200:
        return value / 100.0
    return value


def _ts_to_datetime(raw_ts: Any) -> datetime | None:
    if raw_ts in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _coordinate_origin(samples: list[dict[str, Any]]) -> tuple[float, float] | None:
    for sample in samples:
        lat = sample.get("lat")
        lng = sample.get("lng")
        if lat is not None and lng is not None:
            return float(lat), float(lng)
    return None


def _local_xy_m(lat: float, lng: float, origin: tuple[float, float]) -> tuple[float, float]:
    origin_lat, origin_lng = origin
    mean_lat = math.radians((origin_lat + lat) / 2)
    x_m = math.radians(lng - origin_lng) * 6371000.0 * math.cos(mean_lat)
    y_m = math.radians(lat - origin_lat) * 6371000.0
    return x_m, y_m


def _is_relative_altitude_frame(frame: int | None) -> bool:
    return frame in {3, 6, 10, 11}


def _detect_takeoff_and_landing(samples: list[dict[str, Any]]) -> tuple[datetime | None, datetime | None, bool]:
    if not samples:
        return None, None, True

    base_altitude = samples[0]["altitude"] or 0.0
    for sample in samples:
        altitude = sample["altitude"]
        sample["relative_altitude"] = (altitude - base_altitude) if altitude is not None else None

    takeoff_at = None
    threshold_started_at = None
    for sample in samples:
        rel_alt = sample["relative_altitude"]
        if rel_alt is not None and rel_alt >= 1.0:
            if threshold_started_at is None:
                threshold_started_at = sample["timestamp"]
            if (sample["timestamp"] - threshold_started_at).total_seconds() >= 3:
                takeoff_at = threshold_started_at
                break
        else:
            threshold_started_at = None

    landing_at = None
    threshold_ended_at = None
    for sample in reversed(samples):
        rel_alt = sample["relative_altitude"]
        speed = sample["speed"]
        speed_ok = speed is None or speed <= 1.5
        if rel_alt is not None and rel_alt <= 0.5 and speed_ok:
            if threshold_ended_at is None:
                threshold_ended_at = sample["timestamp"]
            if (threshold_ended_at - sample["timestamp"]).total_seconds() >= 3:
                landing_at = threshold_ended_at
                break
        else:
            threshold_ended_at = None

    review_required = takeoff_at is None or landing_at is None
    return takeoff_at, landing_at, review_required


def _build_altitude_profile(samples: list[dict[str, Any]], max_points: int = 180) -> list[dict[str, Any]]:
    valid_samples = [
        sample
        for sample in samples
        if sample.get("timestamp") is not None and sample.get("altitude") is not None
    ]
    if not valid_samples:
        return []

    first_timestamp = valid_samples[0]["timestamp"]
    base_altitude = float(valid_samples[0]["altitude"])
    origin = _coordinate_origin(valid_samples)
    step = max(math.ceil(len(valid_samples) / max_points), 1)
    sampled = valid_samples[::step]
    if sampled[-1] is not valid_samples[-1]:
        sampled.append(valid_samples[-1])

    profile: list[dict[str, Any]] = []
    for sample in sampled:
        timestamp = sample["timestamp"]
        altitude = float(sample["altitude"])
        speed = sample.get("speed")
        lat = sample.get("lat")
        lng = sample.get("lng")
        time_s = max((timestamp - first_timestamp).total_seconds(), 0.0)
        if origin and lat is not None and lng is not None:
            x_m, y_m = _local_xy_m(float(lat), float(lng), origin)
        else:
            x_m, y_m = time_s, 0.0
        point = {
            "time_s": round(time_s, 2),
            "altitude_m": round(altitude, 2),
            "relative_altitude_m": round(altitude - base_altitude, 2),
            "speed_mps": round(float(speed), 2) if speed is not None else None,
            "x_m": round(x_m, 2),
            "y_m": round(y_m, 2),
        }
        if lat is not None and lng is not None:
            point["lat"] = round(float(lat), 7)
            point["lng"] = round(float(lng), 7)
        profile.append(point)
    return profile


def _build_waypoints(
    waypoint_samples: list[dict[str, Any]],
    timeline_samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not waypoint_samples:
        return []

    origin = _coordinate_origin(timeline_samples) or _coordinate_origin(waypoint_samples)
    altitude_samples = [sample for sample in timeline_samples if sample.get("altitude") is not None]
    base_altitude = float(altitude_samples[0]["altitude"]) if altitude_samples else 0.0
    waypoints: list[dict[str, Any]] = []

    for sample in sorted(waypoint_samples, key=lambda item: item.get("seq") if item.get("seq") is not None else 999999):
        lat = sample.get("lat")
        lng = sample.get("lng")
        if lat is None or lng is None:
            continue
        altitude = sample.get("altitude")
        frame = sample.get("frame")
        altitude_value = float(altitude) if altitude is not None else base_altitude
        relative_altitude = altitude_value if _is_relative_altitude_frame(frame) else altitude_value - base_altitude
        x_m, y_m = _local_xy_m(float(lat), float(lng), origin) if origin else (0.0, 0.0)
        seq = sample.get("seq")
        waypoints.append(
            {
                "seq": int(seq) if seq is not None else len(waypoints),
                "command": sample.get("command"),
                "frame": frame,
                "lat": round(float(lat), 7),
                "lng": round(float(lng), 7),
                "altitude_m": round(altitude_value, 2),
                "relative_altitude_m": round(relative_altitude, 2),
                "x_m": round(x_m, 2),
                "y_m": round(y_m, 2),
            }
        )
    return waypoints


def parse_log_file(file_path: Path) -> ParsedFlightLog:
    suffix = file_path.suffix.lower()
    if suffix == ".bin":
        reader = DFReader.DFReader_binary(str(file_path))
    elif suffix == ".log":
        reader = DFReader.DFReader_text(str(file_path))
    else:
        raise ValueError("Unsupported log format")

    parsed = ParsedFlightLog()
    timeline_samples: list[dict[str, Any]] = []
    waypoint_samples: list[dict[str, Any]] = []
    waypoint_keys: set[tuple[Any, ...]] = set()
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    current_mode: str | None = None
    current_mode_started: datetime | None = None

    while True:
        message = reader.recv_msg()
        if message is None:
            break

        timestamp = _ts_to_datetime(getattr(message, "_timestamp", None))
        if timestamp is None:
            continue

        first_timestamp = first_timestamp or timestamp
        last_timestamp = timestamp
        message_type = message.get_type()

        if message_type == "MODE":
            new_mode = _safe_text(message, ["Mode", "mode"])
            if new_mode:
                if current_mode and current_mode_started:
                    parsed.mode_spans.append(
                        ParsedModeSpan(
                            mode_name=current_mode,
                            start_at_utc=current_mode_started,
                            end_at_utc=timestamp,
                            duration_seconds=max(int((timestamp - current_mode_started).total_seconds()), 0),
                        )
                    )
                current_mode = new_mode
                current_mode_started = timestamp

        if message_type in {"GPS", "GPS2", "POS"}:
            lat = _normalize_coord(_safe_float(message, ["Lat", "lat"]), 90)
            lng = _normalize_coord(_safe_float(message, ["Lng", "Lon", "lng", "lon"]), 180)
            alt = _normalize_altitude(_safe_float(message, ["RelAlt", "Alt", "RAlt", "RelHomeAlt"]))
            speed = _normalize_speed(_safe_float(message, ["Spd", "GSpd", "Speed"]))
            satellites = _safe_int(message, ["NSats", "Sats", "Sat"])
            hdop = _safe_float(message, ["HDop", "HDOP"])

            if lat is not None and lng is not None:
                parsed.takeoff_lat = parsed.takeoff_lat if parsed.takeoff_lat is not None else lat
                parsed.takeoff_lng = parsed.takeoff_lng if parsed.takeoff_lng is not None else lng
                parsed.landing_lat = lat
                parsed.landing_lng = lng

            if alt is not None:
                parsed.max_altitude_m = max(parsed.max_altitude_m or alt, alt)
            if speed is not None:
                parsed.max_speed_mps = max(parsed.max_speed_mps or speed, speed)
            if satellites is not None:
                parsed.gps_min_satellites = satellites if parsed.gps_min_satellites is None else min(parsed.gps_min_satellites, satellites)
            if hdop is not None:
                parsed.gps_max_hdop = hdop if parsed.gps_max_hdop is None else max(parsed.gps_max_hdop, hdop)

            if lat is not None and lng is not None and parsed.takeoff_lat is not None and parsed.takeoff_lng is not None:
                distance_m = _haversine_m(parsed.takeoff_lat, parsed.takeoff_lng, lat, lng)
                parsed.max_distance_m = max(parsed.max_distance_m or distance_m, distance_m)

            timeline_samples.append(
                {
                    "timestamp": timestamp,
                    "altitude": alt,
                    "speed": speed,
                    "lat": lat,
                    "lng": lng,
                }
            )

        if message_type == "CMD":
            seq = _safe_int(message, ["CNum", "Seq", "Num"])
            command = _safe_int(message, ["CId", "Cmd", "Command"])
            frame = _safe_int(message, ["Frame"])
            lat = _normalize_coord(_safe_float(message, ["Lat", "lat"]), 90)
            lng = _normalize_coord(_safe_float(message, ["Lng", "Lon", "lng", "lon"]), 180)
            altitude = _normalize_altitude(_safe_float(message, ["Alt", "Altitude"]))
            if lat is not None and lng is not None and abs(lat) > 0.000001 and abs(lng) > 0.000001:
                key = (
                    seq,
                    command,
                    frame,
                    round(lat, 7),
                    round(lng, 7),
                    round(altitude or 0.0, 2),
                )
                if key not in waypoint_keys:
                    waypoint_keys.add(key)
                    waypoint_samples.append(
                        {
                            "seq": seq,
                            "command": command,
                            "frame": frame,
                            "lat": lat,
                            "lng": lng,
                            "altitude": altitude,
                        }
                    )

        if message_type in {"BAT", "BATT", "CURR"}:
            voltage = _safe_float(message, ["Volt", "VoltR", "V"])
            current = _safe_float(message, ["Curr", "Current", "I"])
            consumed = _safe_float(message, ["CurrTot", "Consumed", "Mah"])
            if voltage is not None:
                parsed.battery_start_voltage = parsed.battery_start_voltage or voltage
                parsed.battery_end_voltage = voltage
                parsed.battery_min_voltage = voltage if parsed.battery_min_voltage is None else min(parsed.battery_min_voltage, voltage)
            if current is not None:
                parsed.battery_max_current = current if parsed.battery_max_current is None else max(parsed.battery_max_current, current)
            if consumed is not None:
                parsed.battery_consumed_mah = consumed

        if message_type in {"ERR", "MSG"}:
            text = _safe_text(message, ["Message", "Text", "Subsys"])
            if text:
                parsed.error_messages.append(text)

    if current_mode and current_mode_started and last_timestamp:
        parsed.mode_spans.append(
            ParsedModeSpan(
                mode_name=current_mode,
                start_at_utc=current_mode_started,
                end_at_utc=last_timestamp,
                duration_seconds=max(int((last_timestamp - current_mode_started).total_seconds()), 0),
            )
        )

    parsed.arm_at_utc = first_timestamp
    parsed.disarm_at_utc = last_timestamp
    parsed.flight_date = first_timestamp.date() if first_timestamp else None

    takeoff_at, landing_at, review_required = _detect_takeoff_and_landing(timeline_samples)
    parsed.takeoff_at_utc = takeoff_at or first_timestamp
    parsed.landing_at_utc = landing_at or last_timestamp
    parsed.takeoff_detected_by = "relative_altitude_threshold" if takeoff_at else "timestamp_fallback"
    parsed.landing_detected_by = "relative_altitude_and_speed_threshold" if landing_at else "timestamp_fallback"
    parsed.review_required = review_required

    if parsed.takeoff_at_utc and parsed.landing_at_utc:
        parsed.duration_seconds = max(int((parsed.landing_at_utc - parsed.takeoff_at_utc).total_seconds()), 0)

    if parsed.gps_min_satellites is not None and parsed.gps_min_satellites < 8:
        parsed.warning_messages.append(f"GPS衛星数が少ない可能性があります: min={parsed.gps_min_satellites}")
    if parsed.gps_max_hdop is not None and parsed.gps_max_hdop > 2.5:
        parsed.warning_messages.append(f"HDOPが悪化しています: max={parsed.gps_max_hdop:.2f}")
    if parsed.battery_min_voltage is not None and parsed.battery_min_voltage < 13.5:
        parsed.warning_messages.append(f"最低電圧が低めです: min={parsed.battery_min_voltage:.2f}V")
    if review_required:
        parsed.warning_messages.append("離陸または着陸時刻の自動判定信頼度が低いため確認が必要です。")

    if parsed.error_messages:
        parsed.diagnostic_grade = FlightRecord.DiagnosticGrade.DANGER
    elif parsed.warning_messages:
        parsed.diagnostic_grade = FlightRecord.DiagnosticGrade.WARNING
    else:
        parsed.diagnostic_grade = FlightRecord.DiagnosticGrade.NORMAL

    parsed.ekf_summary = "重大なEKFイベントは検出されませんでした。"
    parsed.vibration_summary = "振動データの高度な解析はMVPでは簡易判定です。"
    altitude_profile = _build_altitude_profile(timeline_samples)
    waypoints = _build_waypoints(waypoint_samples, timeline_samples)
    parsed.summary_json = {
        "mode_count": len(parsed.mode_spans),
        "warning_count": len(parsed.warning_messages),
        "error_count": len(parsed.error_messages),
        "altitude_profile": altitude_profile,
        "altitude_profile_count": len(altitude_profile),
        "waypoints": waypoints,
        "waypoint_count": len(waypoints),
    }
    return parsed


def apply_analysis(record: FlightRecord, parsed: ParsedFlightLog) -> FlightRecord:
    record.flight_date = parsed.flight_date
    record.takeoff_at_utc = parsed.takeoff_at_utc
    record.landing_at_utc = parsed.landing_at_utc
    record.duration_seconds = parsed.duration_seconds
    record.takeoff_lat = parsed.takeoff_lat
    record.takeoff_lng = parsed.takeoff_lng
    record.landing_lat = parsed.landing_lat
    record.landing_lng = parsed.landing_lng
    record.takeoff_address = reverse_geocode(parsed.takeoff_lat, parsed.takeoff_lng)
    record.landing_address = reverse_geocode(parsed.landing_lat, parsed.landing_lng)
    record.review_required = parsed.review_required
    record.diagnostic_grade = parsed.diagnostic_grade
    record.analysis_error = ""

    weather = get_weather_reference(parsed.takeoff_lat, parsed.takeoff_lng, parsed.takeoff_at_utc)
    for key, value in weather.items():
        setattr(record, key, value)

    record.status = FlightRecord.Status.DRAFT
    record.save()

    FlightAnalysis.objects.update_or_create(
        flight_record=record,
        defaults={
            "arm_at_utc": parsed.arm_at_utc,
            "disarm_at_utc": parsed.disarm_at_utc,
            "takeoff_detected_by": parsed.takeoff_detected_by,
            "landing_detected_by": parsed.landing_detected_by,
            "max_altitude_m": parsed.max_altitude_m,
            "max_speed_mps": parsed.max_speed_mps,
            "max_distance_m": parsed.max_distance_m,
            "battery_start_voltage": parsed.battery_start_voltage,
            "battery_end_voltage": parsed.battery_end_voltage,
            "battery_min_voltage": parsed.battery_min_voltage,
            "battery_max_current": parsed.battery_max_current,
            "battery_consumed_mah": parsed.battery_consumed_mah,
            "gps_min_satellites": parsed.gps_min_satellites,
            "gps_max_hdop": parsed.gps_max_hdop,
            "ekf_summary": parsed.ekf_summary,
            "vibration_summary": parsed.vibration_summary,
            "failsafe_events": parsed.failsafe_events,
            "warning_messages": parsed.warning_messages,
            "error_messages": parsed.error_messages,
            "summary_json": parsed.summary_json,
        },
    )

    FlightModeSpan.objects.filter(flight_record=record).delete()
    FlightModeSpan.objects.bulk_create(
        [
            FlightModeSpan(
                flight_record=record,
                mode_name=mode.mode_name,
                start_at_utc=mode.start_at_utc,
                end_at_utc=mode.end_at_utc,
                duration_seconds=mode.duration_seconds,
            )
            for mode in parsed.mode_spans
        ]
    )
    return record


def _aircraft_snapshot(record: FlightRecord) -> dict[str, Any]:
    aircraft = record.aircraft
    if aircraft is None:
        return {}
    return {
        "registration_number": aircraft.registration_number,
        "model": aircraft.model,
        "serial_number": aircraft.serial_number,
        "name": aircraft.name,
        "initial_total_flight_seconds": aircraft.initial_total_flight_seconds,
        "current_total_flight_seconds": aircraft.current_total_flight_seconds,
    }


def _pilot_snapshot(record: FlightRecord) -> dict[str, Any]:
    pilot = record.pilot
    if pilot is None:
        return {}
    return {
        "name": pilot.name,
        "license_number": pilot.license_number,
        "organization": pilot.organization,
        "signature_image": pilot.signature_image.url if pilot.signature_image else "",
    }


def _require_finalize_fields(record: FlightRecord) -> None:
    if record.aircraft_id is None:
        raise ValueError("機体を選択してください。")
    if record.pilot_id is None:
        raise ValueError("操縦者を選択してください。")
    if not record.official_weather:
        raise ValueError("正式な気象を入力してください。")
    if record.official_temperature_c is None:
        raise ValueError("正式な気温を入力してください。")
    if record.official_wind_speed_mps is None:
        raise ValueError("正式な風速を入力してください。")


def generate_pdf_asset(record: FlightRecord) -> GeneratedAsset:
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Japanese", fontName="HeiseiKakuGo-W5", fontSize=10, leading=14))
    styles.add(ParagraphStyle(name="JapaneseTitle", fontName="HeiseiKakuGo-W5", fontSize=16, leading=20))

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    story = [
        Paragraph("ArduPilot Flight Record", styles["JapaneseTitle"]),
        Spacer(1, 6 * mm),
    ]

    summary_rows = [
        ["記録ID", str(record.pk)],
        ["状態", record.get_status_display()],
        ["飛行日", record.flight_date.isoformat() if record.flight_date else ""],
        ["離陸時刻", record.takeoff_at_utc.astimezone(dj_timezone.get_current_timezone()).strftime("%Y-%m-%d %H:%M:%S") if record.takeoff_at_utc else ""],
        ["着陸時刻", record.landing_at_utc.astimezone(dj_timezone.get_current_timezone()).strftime("%Y-%m-%d %H:%M:%S") if record.landing_at_utc else ""],
        ["飛行時間(秒)", str(record.duration_seconds or 0)],
        ["総合判定", record.diagnostic_grade],
    ]
    summary_table = Table(summary_rows, colWidths=[35 * mm, 145 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "HeiseiKakuGo-W5"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#d8e9f7")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9cb5c7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 6 * mm)])

    official_rows = [
        ["正式気象", record.official_weather],
        ["正式気温", "" if record.official_temperature_c is None else f"{record.official_temperature_c:.1f} ℃"],
        ["正式風速", "" if record.official_wind_speed_mps is None else f"{record.official_wind_speed_mps:.1f} m/s"],
        ["離陸場所", record.takeoff_address],
        ["着陸場所", record.landing_address],
        ["飛行概要", record.purpose or ""],
        ["記事", record.article_notes or ""],
    ]
    official_table = Table(official_rows, colWidths=[35 * mm, 145 * mm])
    official_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "HeiseiKakuGo-W5"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e9f7ee")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94b7a4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([official_table, Spacer(1, 6 * mm)])

    reference_rows = [
        ["参考気象", record.reference_weather or "参考値なし"],
        ["参考気温", "" if record.reference_temperature_c is None else f"{record.reference_temperature_c:.1f} ℃"],
        ["参考風速", "" if record.reference_wind_speed_mps is None else f"{record.reference_wind_speed_mps:.1f} m/s"],
        ["観測所", record.reference_station_name or ""],
        ["出典", record.reference_source or ""],
    ]
    reference_table = Table(reference_rows, colWidths=[35 * mm, 145 * mm])
    reference_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "HeiseiKakuGo-W5"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f6fa")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c3ce")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([reference_table, Spacer(1, 4 * mm)])
    story.append(Paragraph("※ 参考値は正式記録ではありません。正式値は操縦者入力です。", styles["Japanese"]))

    analysis = record.analysis if hasattr(record, "analysis") else None
    if analysis is not None:
        story.extend([Spacer(1, 6 * mm), Paragraph("解析サマリ", styles["JapaneseTitle"])])
        for message in analysis.warning_messages:
            story.append(Paragraph(f"・{message}", styles["Japanese"]))
        for message in analysis.error_messages:
            story.append(Paragraph(f"・{message}", styles["Japanese"]))

        summary_json = analysis.summary_json or {}
        altitude_chart = AltitudeProfile3DChart(
            summary_json.get("altitude_profile") or [],
            summary_json.get("waypoints") or [],
        )
        if altitude_chart.has_data:
            story.extend([Spacer(1, 5 * mm), altitude_chart])

    document.build(story)
    payload = buffer.getvalue()
    filename = f"flight_record_{record.pk}_{dj_timezone.now().strftime('%Y%m%d%H%M%S')}.pdf"
    asset = GeneratedAsset.objects.create(
        flight_record=record,
        asset_type=GeneratedAsset.AssetType.PDF,
        file=ContentFile(payload, name=filename),
    )
    return asset


def finalize_flight_record(record: FlightRecord) -> tuple[FlightRecord, GeneratedAsset]:
    _require_finalize_fields(record)
    with transaction.atomic():
        locked = FlightRecord.objects.select_for_update().select_related("aircraft", "pilot").get(pk=record.pk)
        _require_finalize_fields(locked)
        locked.aircraft_snapshot = _aircraft_snapshot(locked)
        locked.pilot_snapshot = _pilot_snapshot(locked)
        locked.status = FlightRecord.Status.FINALIZED
        if locked.finalized_at is None:
            locked.finalized_at = dj_timezone.now()
        locked.save()

        ledger, created = FlightTimeLedger.objects.get_or_create(
            flight_record=locked,
            defaults={
                "aircraft": locked.aircraft,
                "added_seconds": locked.duration_seconds or 0,
            },
        )
        if created and locked.aircraft_id:
            locked.aircraft.__class__.objects.filter(pk=locked.aircraft_id).update(
                current_total_flight_seconds=F("current_total_flight_seconds") + ledger.added_seconds
            )

        asset = generate_pdf_asset(locked)
    return locked, asset
