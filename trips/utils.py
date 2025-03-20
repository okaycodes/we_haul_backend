from datetime import timedelta
import math
import openrouteservice
from django.conf import settings

ORS_API_KEY = settings.OPENROUTESERVICE_API_KEY


def get_route_info(start_coords, end_coords):
    """Fetch route information from OpenRouteService"""
    client = openrouteservice.Client(key=ORS_API_KEY)

    try:
        route = client.directions(
            coordinates=[start_coords, end_coords],
            profile="driving-hgv",  # Heavy Goods Vehicle profile
            format="geojson",
        )

        distance_meters = route["features"][0]["properties"]["segments"][0]["distance"]
        duration_seconds = route["features"][0]["properties"]["segments"][0]["duration"]
        coordinates = route["features"][0]["geometry"]["coordinates"]
        reversed_coordinates = [
            sublist[::-1] for sublist in coordinates
        ]  # Convert [lon, lat] -> [lat, lon]

        return {
            "distance_miles": distance_meters / 1609.34,
            "duration_hours": duration_seconds / 3600,
            "coordinates": reversed_coordinates,
        }
    except Exception as e:
        print(f"Error fetching route: {e}")
        return None


def geocode_location(address):
    """Convert an address to longitude/latitude using OpenRouteService"""
    client = openrouteservice.Client(key=ORS_API_KEY)
    try:
        result = client.pelias_search(text=address)

        coordinates = result["features"][0]["geometry"]["coordinates"]
        return coordinates
    except Exception as e:
        print(f"Geocoding error for {address}: {e}")
        return None


def round_to_nearest_15_minutes(hours: float):
    """Round a float (in hours) up to the nearest 15-minute mark and convert to timedelta."""
    total_minutes = hours * 60  # Convert hours to minutes
    rounded_minutes = math.ceil(total_minutes / 15) * 15
    return rounded_minutes


class Status:
    OFF_DUTY = "OFF DUTY"
    SLEEPER_BERTH = "SLEEPER BERTH"
    DRIVING = "DRIVING"
    ON_DUTY = "ON DUTY"


class Action:
    PRE_CHECK = "PRE CHECK"
    DRIVING = "DRIVING"
    PICKUP = "PICKUP"
    BREAK = "BREAK"
    REST_STOP = "REST STOP"
    FUEL_STOP = "FUEL STOP"
    OFF_DAYS = "OFF DAYS"
    DROP_OFF = "DROP OFF"
    DONE = "DONE"
