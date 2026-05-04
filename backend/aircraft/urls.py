from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import AircraftViewSet

router = DefaultRouter()
router.register("aircraft", AircraftViewSet, basename="aircraft")

urlpatterns = router.urls
