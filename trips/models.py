import uuid
from django.db import models


class Trip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    start_location = models.CharField(max_length=255)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    current_cycle_hours_used = models.FloatField()
    distance_miles = models.FloatField()
    duration_hours = models.FloatField()
    route_data = models.JSONField()

    def __str__(self):
        return f"Trip {self.id}"


# class Stop(models.Model):
#     STOP_TYPES = [
#         ("break", "Break"),
#         ("fuel", "Fuel"),
#         ("sleeper-berth", "Sleeper Berth"),
#         ("rest", "Rest"),
#         ("pickup", "Pickup"),
#         ("dropoff", "Dropoff"),
#     ]

#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="stops")
#     stop_type = models.CharField(max_length=20, choices=STOP_TYPES)
#     location = models.CharField(max_length=255)
#     scheduled_time = models.DateTimeField()

#     def __str__(self):
#         return f"{self.get_stop_type_display()} at {self.location}"


class ELDLog(models.Model):
    STATUS_CHOICES = [
        ("OFF_DUTY", "OFF_DUTY"),
        ("SLEEPER_BERTH", "SLEEPER_BERTH"),
        ("DRIVING", "DRIVING"),
        ("ON_DUTY", "ON_DUTY"),
    ]

    ACTION_CHOICES = [
        ("PRE_CHECK", "PRE_CHECK"),
        ("DRIVING", "DRIVING"),
        ("PICKUP", "PICKUP"),
        ("BREAK", "BREAK"),
        ("FUEL_STOP", "FUEL_STOP"),
        ("OFF_DAYS", "OFF_DAYS"),
        ("DROP_OFF", "DROP_OFF"),
        ("DONE", "DONE"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="eld_logs")
    timestamp = models.DateTimeField()
    timespent = models.FloatField()
    status = models.CharField(max_length=255, choices=STATUS_CHOICES)
    action = models.CharField(max_length=255, choices=ACTION_CHOICES)
    coordinates = models.JSONField()

    def __str__(self):
        return f"ELD Log for Trip {self.trip.id} on {self.timestamp}"
