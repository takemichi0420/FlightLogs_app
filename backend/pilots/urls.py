from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import PilotViewSet

router = DefaultRouter()
router.register("pilots", PilotViewSet, basename="pilot")

urlpatterns = router.urls
