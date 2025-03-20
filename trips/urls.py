from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ELDLogViewSet, TripViewSet

router = DefaultRouter()
router.register(r"trips", TripViewSet)
router.register(r"eld-logs", ELDLogViewSet, basename="eldlog")


urlpatterns = [
    path("", include(router.urls)),
]
