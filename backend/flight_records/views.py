from __future__ import annotations

from pathlib import Path

from django.core.files.base import ContentFile
from django.http import FileResponse
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from aircraft.models import Aircraft
from pilots.models import Pilot

from .mavlink_import import MavlinkImportError, download_mavlink_log, list_mavlink_logs
from .models import AnalysisJob, FlightRecord, GeneratedAsset
from .serializers import (
    AnalysisJobSerializer,
    FlightRecordSerializer,
    LogUploadSerializer,
    MavlinkConnectionSerializer,
    MavlinkLogImportSerializer,
)
from .services import finalize_flight_record, generate_pdf_asset, reverse_geocode
from .tasks import dispatch_analysis_job


def _get_owned_aircraft(user, aircraft_id):
    if aircraft_id is None:
        return None
    aircraft = Aircraft.objects.filter(owner=user, pk=aircraft_id).first()
    if aircraft is None:
        raise ValidationError({"aircraft_id": "自分の機体のみ指定できます。"})
    return aircraft


def _get_owned_pilot(user, pilot_id):
    if pilot_id is None:
        return None
    pilot = Pilot.objects.filter(owner=user, pk=pilot_id).first()
    if pilot is None:
        raise ValidationError({"pilot_id": "自分の操縦者のみ指定できます。"})
    return pilot


class LogUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = LogUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        upload = serializer.validated_data["file"]
        aircraft = _get_owned_aircraft(request.user, serializer.validated_data.get("aircraft_id"))
        pilot = _get_owned_pilot(request.user, serializer.validated_data.get("pilot_id"))

        record = FlightRecord.objects.create(
            owner=request.user,
            aircraft=aircraft,
            pilot=pilot,
            status=FlightRecord.Status.ANALYZING,
            source_file=upload,
            source_original_name=upload.name,
            source_log_type=Path(upload.name).suffix.lower().lstrip("."),
            vehicle_type=serializer.validated_data["vehicle_type"],
        )
        job = AnalysisJob.objects.create(flight_record=record)
        dispatch_analysis_job(job.pk)
        return Response(AnalysisJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class MavlinkLogListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = MavlinkConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            logs = list_mavlink_logs(
                connection=serializer.validated_data["connection"],
                baud=serializer.validated_data["baud"],
                timeout_s=serializer.validated_data["timeout_s"],
            )
        except MavlinkImportError as exc:
            raise ValidationError({"connection": str(exc)}) from exc
        return Response({"logs": [entry.to_dict() for entry in logs]})


class MavlinkLogImportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = MavlinkLogImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        aircraft = _get_owned_aircraft(request.user, serializer.validated_data.get("aircraft_id"))
        pilot = _get_owned_pilot(request.user, serializer.validated_data.get("pilot_id"))

        try:
            downloaded = download_mavlink_log(
                connection=serializer.validated_data["connection"],
                baud=serializer.validated_data["baud"],
                timeout_s=serializer.validated_data["timeout_s"],
                log_id=serializer.validated_data.get("log_id"),
            )
        except MavlinkImportError as exc:
            raise ValidationError({"connection": str(exc)}) from exc

        filename = f"mavlink_log_{downloaded.entry.id}.bin"
        record = FlightRecord.objects.create(
            owner=request.user,
            aircraft=aircraft,
            pilot=pilot,
            status=FlightRecord.Status.ANALYZING,
            source_file=ContentFile(downloaded.payload, name=filename),
            source_original_name=filename,
            source_log_type="bin",
            vehicle_type=serializer.validated_data["vehicle_type"],
        )
        job = AnalysisJob.objects.create(flight_record=record)
        dispatch_analysis_job(job.pk)
        return Response(AnalysisJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class AnalysisJobDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, pk) -> Response:
        job = AnalysisJob.objects.select_related("flight_record").filter(pk=pk, flight_record__owner=request.user).first()
        if job is None:
            return Response({"code": "not_found", "message": "ジョブが見つかりません。"}, status=status.HTTP_404_NOT_FOUND)
        return Response(AnalysisJobSerializer(job).data)


class FlightRecordViewSet(viewsets.ModelViewSet):
    serializer_class = FlightRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering_fields = ["created_at", "flight_date", "status"]
    search_fields = ["source_original_name", "takeoff_address", "landing_address", "purpose"]

    def get_queryset(self):
        return (
            FlightRecord.objects.filter(owner=self.request.user)
            .select_related("aircraft", "pilot", "analysis_job", "analysis")
            .prefetch_related("mode_spans", "generated_assets")
        )

    def perform_update(self, serializer):
        if self.get_object().status == FlightRecord.Status.FINALIZED:
            raise ValidationError("確定済み飛行記録は編集できません。")
        serializer.save()

    @action(detail=True, methods=["post"], url_path="refresh-addresses")
    def refresh_addresses(self, request: Request, pk=None) -> Response:
        record = self.get_object()
        if record.takeoff_lat is not None and record.takeoff_lng is not None:
            record.takeoff_address = reverse_geocode(record.takeoff_lat, record.takeoff_lng)
        if record.landing_lat is not None and record.landing_lng is not None:
            record.landing_address = reverse_geocode(record.landing_lat, record.landing_lng)
        record.save(update_fields=["takeoff_address", "landing_address", "updated_at"])
        return Response(self.get_serializer(record).data)

    @action(detail=True, methods=["post"])
    def finalize(self, request: Request, pk=None) -> Response:
        record = self.get_object()
        record, asset = finalize_flight_record(record)
        serializer = self.get_serializer(record)
        response = serializer.data
        response["latest_pdf_asset_id"] = asset.id
        return Response(response)

    @action(detail=True, methods=["post"], url_path="generate-pdf")
    def generate_pdf(self, request: Request, pk=None) -> Response:
        record = self.get_object()
        asset = generate_pdf_asset(record)
        return Response({"asset_id": asset.id, "file": asset.file.url}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="download-pdf")
    def download_pdf(self, request: Request, pk=None):
        record = self.get_object()
        asset = record.generated_assets.filter(asset_type=GeneratedAsset.AssetType.PDF).first()
        if asset is None:
            return Response({"code": "not_found", "message": "PDFがまだ生成されていません。"}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(asset.file.open("rb"), as_attachment=True, filename=Path(asset.file.name).name)
