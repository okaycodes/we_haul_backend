from .utils import (
    Action,
    Status,
    get_route_info,
    geocode_location,
    round_to_nearest_15_minutes,
)

from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Trip, ELDLog
from .serializers import TripSerializer, ELDLogSerializer
from datetime import timedelta
import pandas as pd


class TripViewSet(viewsets.ModelViewSet):
    """API endpoint for managing trips and generating route info"""

    queryset = Trip.objects.all()
    serializer_class = TripSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            trip_data = serializer.validated_data

            # Fetch route info from OpenRouteService
            start_coords = geocode_location(trip_data["start_location"])
            pickup_coords = geocode_location(trip_data["pickup_location"])
            end_coords = geocode_location(trip_data["dropoff_location"])

            pickup_route_info = get_route_info(start_coords, pickup_coords)
            route_info = get_route_info(start_coords, end_coords)

            if route_info is None:
                return Response(
                    {"error": "Failed to fetch route information"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Save trip with route details
            trip = Trip.objects.create(
                start_location=trip_data["start_location"],
                pickup_location=trip_data["pickup_location"],
                dropoff_location=trip_data["dropoff_location"],
                start_time=trip_data["start_time"],
                current_cycle_hours_used=trip_data["current_cycle_hours_used"],
                distance_miles=route_info["distance_miles"],
                duration_hours=route_info["duration_hours"],
                route_data={"coordinates": route_info["coordinates"]},
            )

            eld_logs = self.generate_eld_logs(
                trip=trip,
                pickup_travel_time=round_to_nearest_15_minutes(
                    pickup_route_info["duration_hours"]
                ),
                total_travel_time=round_to_nearest_15_minutes(
                    route_info["duration_hours"]
                ),
                coordinates=route_info["coordinates"],
            )

            return Response(
                {
                    "trip": TripSerializer(trip).data,
                    "eld_logs": ELDLogSerializer(eld_logs, many=True).data,
                },
                status=status.HTTP_201_CREATED,
            )

        print(serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def generate_eld_logs(
        self,
        trip,
        pickup_travel_time,
        total_travel_time,
        coordinates,
    ):
        logs = []

        # round the start time to the nearest 15 minutes
        current_time = pd.Timestamp(trip.start_time).round("15min")

        # total travel time in minutes
        remaining_drive_time = total_travel_time

        has_picked_up = False

        # Time to pickup in minutes
        time_to_pickup = pickup_travel_time

        # Maximum continuous drive time in minutes (before 30-min break)
        time_to_next_break = 8 * 60

        # Maximum cumulative drive time in minutes (before 10 hours rest)
        time_to_next_rest = 11 * 60

        # Maximum cumulative drive time in minutes (before 70hr/8d rest)
        time_to_next_off = 70 * 60 - trip.current_cycle_hours_used * 60

        # Maximum cumulative drive time before refuel (avg speed of 55/hr)
        time_to_next_refuel = round_to_nearest_15_minutes(1000 / 55)

        route_location = coordinates[0]

        # Step 1: Vehicular pre-checks
        log_entry = self._add_log_entry(
            trip=trip,
            time_stamp=current_time,
            timespent=0,
            status=Status.ON_DUTY,
            action=Action.PRE_CHECK,
            location=route_location,
        )
        logs.append(log_entry)

        current_time += timedelta(minutes=30)

        while remaining_drive_time > 0:
            # Max Possible Drive, only consider time_to_pickup while !has_picked_up
            checking_values = [
                time_to_next_break,
                time_to_next_rest,
                time_to_next_off,
                time_to_next_refuel,
                remaining_drive_time,
            ]

            max_possible_drive = (
                min(*checking_values)
                if has_picked_up
                else min(*checking_values, time_to_pickup)
            )

            remaining_drive_time -= max_possible_drive
            time_to_next_break -= max_possible_drive
            time_to_next_rest -= max_possible_drive
            time_to_pickup -= max_possible_drive
            time_to_next_off -= max_possible_drive
            time_to_next_refuel -= max_possible_drive

            # Step 2: Add driving Log
            log_entry = self._add_log_entry(
                trip=trip,
                time_stamp=current_time,
                timespent=max_possible_drive,
                status=Status.DRIVING,
                action=Action.DRIVING,
                location=route_location,
            )
            logs.append(log_entry)

            # recalculate route location, current_time after drive
            routes_len = len(coordinates)
            total_driven = total_travel_time - remaining_drive_time
            percentage_driven = total_driven / total_travel_time
            waypoints_driven = int(routes_len * percentage_driven)
            # find min to ensure it never gets outside list
            route_index = min(waypoints_driven, routes_len - 1)
            route_location = coordinates[route_index]

            current_time += timedelta(minutes=max_possible_drive)

            # Step 3: Add Stop Logs if Stop is reached After Drive

            # pickup log
            if has_picked_up == False and time_to_pickup == 0:
                has_picked_up = True
                log_entry = self._add_log_entry(
                    trip=trip,
                    time_stamp=current_time,
                    timespent=60,
                    status=Status.ON_DUTY,
                    action=Action.PICKUP,
                    location=route_location,
                )
                logs.append(log_entry)

                current_time += timedelta(hours=1)

            # break log after 8 hours of driving
            if time_to_next_break == 0 and remaining_drive_time > 0:
                log_entry = self._add_log_entry(
                    trip=trip,
                    time_stamp=current_time,
                    timespent=30,
                    status=Status.OFF_DUTY,
                    action=Action.BREAK,
                    location=route_location,
                )
                logs.append(log_entry)

                # 30-minute break
                current_time += timedelta(minutes=30)
                time_to_next_break = 8 * 60  # Reset for next session

            # fuel stop log after 1000 miles of driving
            if time_to_next_refuel == 0 and remaining_drive_time > 0:
                log_entry = self._add_log_entry(
                    trip=trip,
                    time_stamp=current_time,
                    timespent=30,
                    status=Status.ON_DUTY,
                    action=Action.FUEL_STOP,
                    location=route_location,
                )
                logs.append(log_entry)

                # 30-minute fuel stop
                current_time += timedelta(minutes=30)
                # reset fuel stop
                time_to_next_refuel = round_to_nearest_15_minutes(1000 / 55)

            # enforce 10-hour reset log after 11 hours of driving
            if time_to_next_rest == 0 and remaining_drive_time > 0:
                log_entry = self._add_log_entry(
                    trip=trip,
                    time_stamp=current_time,
                    timespent=10 * 60,
                    status=Status.SLEEPER_BERTH,
                    action=Action.REST_STOP,
                    location=route_location,
                )
                logs.append(log_entry)

                # 10-hour break
                current_time += timedelta(hours=10)
                time_to_next_rest = 11 * 60  # Reset driving time

            # 70hr/8d limit reached, enforce 34-hour reset log
            if time_to_next_off == 0 and remaining_drive_time > 0:
                log_entry = self._add_log_entry(
                    trip=trip,
                    time_stamp=current_time,
                    timespent=34 * 60,
                    status=Status.OFF_DUTY,
                    action=Action.OFF_DAYS,
                    location=route_location,
                )

                logs.append(log_entry)
                # 34-hour break
                current_time += timedelta(hours=34)
                # Reset all driving time
                time_to_next_break = 8 * 60
                time_to_next_rest = 11 * 60
                time_to_next_off = 70 * 60

        # Step 4: drop off log
        self._add_log_entry(
            trip=trip,
            time_stamp=current_time,
            timespent=60,
            status=Status.ON_DUTY,
            action=Action.DROP_OFF,
            location=route_location,
        )

        # Unloading (1hr)
        current_time += timedelta(hours=1)

        # Step 5: End of trip After Drop Off
        self._add_log_entry(
            trip=trip,
            time_stamp=current_time,
            timespent=0,
            status=Status.OFF_DUTY,
            action=Action.DONE,
            location=route_location,
        )
        return logs

    @staticmethod
    def _add_log_entry(trip, time_stamp, timespent, status, action, location):
        """Add an ELD log entry."""
        log_entry = ELDLog.objects.create(
            trip=trip,
            timestamp=time_stamp,
            timespent=timespent,
            status=status,  # Driving
            action=action,
            coordinates=location,
        )

        return log_entry


class ELDLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows retrieving ELD logs for a given trip.
    """

    serializer_class = ELDLogSerializer

    def get_queryset(self):
        trip_id = self.request.query_params.get("trip_id")
        if trip_id:
            return ELDLog.objects.filter(trip_id=trip_id)
        return ELDLog.objects.none()
