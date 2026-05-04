from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AnalysisJobDetailView, FlightRecordViewSet, LogUploadView, MavlinkLogImportView, MavlinkLogListView

router = DefaultRouter()
router.register("flight-records", FlightRecordViewSet, basename="flight-record")

urlpatterns = [
    path("uploads/logs/", LogUploadView.as_view(), name="log-upload"),
    path("mavlink/logs/", MavlinkLogListView.as_view(), name="mavlink-log-list"),
    path("mavlink/import-log/", MavlinkLogImportView.as_view(), name="mavlink-log-import"),
    path("jobs/<uuid:pk>/", AnalysisJobDetailView.as_view(), name="job-detail"),
]

urlpatterns += router.urls
