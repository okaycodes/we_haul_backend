from rest_framework import serializers
from .models import Trip, ELDLog


class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = "__all__"
        read_only_fields = ("distance_miles", "duration_hours", "route_data")


class ELDLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ELDLog
        fields = "__all__"
