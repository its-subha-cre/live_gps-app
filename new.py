import time
import streamlit as st
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
import folium
import requests
from folium.plugins import MarkerCluster
import pyttsx3
import threading

# OpenRouteService API key and URL
API_KEY = '5b3ce3597851110001cf62482a869d94532f49e488d6ff55d62fda8d'  # Replace with your API key
BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

# Overpass API endpoint for searching tourist spots
OVERPASS_API_URL = "http://overpass-api.de/api/interpreter"

def geocode_with_retry(geolocator, location, retries=3, delay=2):
    """Try geocoding a location with retry logic."""
    for _ in range(retries):
        try:
            return geolocator.geocode(location)
        except GeocoderTimedOut:
            st.warning(f"Geocoding timed out for {location}, retrying...")
            time.sleep(delay)  # Wait for `delay` seconds before retrying
        except GeocoderUnavailable:
            st.warning(f"Geocoder service unavailable for {location}, retrying...")
            time.sleep(delay)
    st.error(f"Geocoding failed for {location} after {retries} retries")
    return None

def get_route_info(start_coords, end_coords):
    """Fetch route information from OpenRouteService API."""
    params = {
        'api_key': API_KEY,
        'start': f'{start_coords[0]},{start_coords[1]}',  # Longitude, Latitude for start
        'end': f'{end_coords[0]},{end_coords[1]}'  # Longitude, Latitude for end
    }

    response = requests.get(BASE_URL, params=params)

    if response.status_code == 200:
        data = response.json()

        # Extract distance and duration from the response
        distance = data['features'][0]['properties']['segments'][0]['distance'] / 1000  # km
        duration = data['features'][0]['properties']['segments'][0]['duration'] / 60  # minutes
        
        # Estimate times for different transportation modes
        walking_duration = duration * 2  # Walking is assumed to take 1.5 times longer
        bus_duration = duration * 1.2  # Bus is assumed to be 1.2 times longer
        
        return distance, duration, walking_duration, bus_duration, data['features'][0]['geometry']['coordinates']
    else:
        raise Exception(f"Error fetching route: {response.status_code} - {response.text}")

def get_tourist_spots(lat, lon, radius=5000):
    """Fetch tourist spots near a location using Overpass API."""
    overpass_query = f"""
    [out:json];
    (
      node["tourism"="attraction"](around:{radius},{lat},{lon});
      way["tourism"="attraction"](around:{radius},{lat},{lon});
      relation["tourism"="attraction"](around:{radius},{lat},{lon});
    );
    out body;
    """
    response = requests.get(OVERPASS_API_URL, params={'data': overpass_query})

    if response.status_code == 200:
        data = response.json()
        tourist_spots = []
        for element in data['elements']:
            if 'tags' in element and 'name' in element['tags']:
                tourist_spots.append(element['tags']['name'])
        return tourist_spots
    else:
        return []

def create_map(source, destination):
    """Create map with source and destination."""
    geolocator = Nominatim(user_agent="my_gps_app", timeout=10)  # Increased timeout to 10 seconds

    # Get location for source and destination with retry logic
    source_location = geocode_with_retry(geolocator, source)
    destination_location = geocode_with_retry(geolocator, destination)

    if not source_location or not destination_location:
        raise Exception("Unable to geocode source or destination")

    # Get the coordinates for routing
    start_coords = (source_location.longitude, source_location.latitude)
    end_coords = (destination_location.longitude, destination_location.latitude)

    # Get the route and distances from OpenRouteService API
    distance, duration, walking_duration, bus_duration, route_coords = get_route_info(start_coords, end_coords)

    # Get tourist spots near the destination
    tourist_spots = get_tourist_spots(destination_location.latitude, destination_location.longitude)

    # Create a map centered between source and destination
    m = folium.Map(location=[(source_location.latitude + destination_location.latitude) / 2,
                             (source_location.longitude + destination_location.longitude) / 2],
                   zoom_start=13)

    # Add markers for source and destination
    folium.Marker([source_location.latitude, source_location.longitude],
                  popup=f"Source: {source}",
                  icon=folium.Icon(color='blue')).add_to(m)
    folium.Marker([destination_location.latitude, destination_location.longitude],
                  popup=f"Destination: {destination}",
                  icon=folium.Icon(color='red')).add_to(m)

    # Add route to the map (polyline)
    folium.PolyLine(locations=[(coord[1], coord[0]) for coord in route_coords],
                    color='green', weight=4).add_to(m)

    return m, distance, duration, walking_duration, bus_duration, tourist_spots

# Function to speak the message using pyttsx3
def speak(message):
    engine = pyttsx3.init()
    engine.say(message)
    engine.runAndWait()

# Streamlit UI
st.title("GPS Location Mapper")

source = st.text_input("Enter Source Location", "Kolkata")
destination = st.text_input("Enter Destination Location", "Delhi")

if st.button("Create Map"):
    try:
        # Create the map based on user input
        map_object, distance, duration, walking_duration, bus_duration, tourist_spots = create_map(source, destination)

        # Display map in Streamlit
        folium_map = map_object._repr_html_()  # Get HTML representation of the map
        st.components.v1.html(folium_map, width=700, height=500)

        # Display distance and time estimates
        st.write(f"**Shortest Distance**: {distance:.2f} km")
        st.write(f"**Time by Car**: {duration:.2f} minutes")
        st.write(f"**Time by Walking**: {walking_duration:.2f} minutes")
        st.write(f"**Time by Bus**: {bus_duration:.2f} minutes")

        # Display tourist spots near the destination
        if tourist_spots:
            st.write("**Tourist Spots near Destination**:")
            for spot in tourist_spots:
                st.write(f"- {spot}")
        else:
            st.write("No tourist spots found near the destination.")
        
        # Simulate tracking logic (based on user input or simulation)
        # You can create a loop to periodically check if the user is on the track.
        tracking_info = st.empty()  # Placeholder to show tracking info
        tracking_info.write("Tracking your location...")

        # Example of user tracking in periodic intervals (simulation)
        time.sleep(5)  # Simulate waiting time

        # Simulated logic - assume the user is within the route
        message = "You are on the shortest path!"
        tracking_info.write(message)
        speak(message)  # Speak the message

    except Exception as e:
        st.error(f"Error: {e}")
