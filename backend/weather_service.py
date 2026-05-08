import os
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_ API_KEY")


def get_weather_forecast(latitude, longitude, days=5):
    url = "https://weather.googleapis.com/v1/forecast/days:lookup"

    params = {
        "key": GOOGLE_API_KEY,
        "location.latitude": latitude,
        "location.longitude": longitude,
        "days": days
    }

    response = requests.get(url, params=params)
    data = response.json()

    print("GOOGLE WEATHER RAW RESPONSE:", data)

    return data