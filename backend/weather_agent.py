import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from city_service import get_city_coordinates
from weather_service import get_weather_forecast

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_weather_recommendations(trip):
    destination_city = trip["destination_city"]

    city_location = get_city_coordinates(destination_city)
    if not city_location:
        raise ValueError(f"Could not find coordinates for destination city: {destination_city}")

    weather_data = get_weather_forecast(
        latitude=city_location["latitude"],
        longitude=city_location["longitude"],
        days=5
    )

    prompt = f"""
You are the Weather Agent for an AI Travel Planner.

Analyze the weather forecast and provide travel planning recommendations.

Destination city:
{destination_city}

Resolved city location:
{json.dumps(city_location, indent=2)}

Weather forecast data:
{json.dumps(weather_data, indent=2)}

Return ONLY valid JSON with this structure:

{{
  "agent": "Weather Agent",
  "destination_city": "{destination_city}",
  "summary": "string",
  "daily_recommendations": [
    {{
      "date": "YYYY-MM-DD",
      "weather_type": "sunny / rainy / cloudy",
      "recommended_activity_type": "indoor / outdoor / mixed",
      "planning_advice": "string"
    }}
  ]
}}

Return ONLY valid JSON.
Do NOT include markdown.
Do NOT include explanations.
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )

    print("WEATHER AGENT RAW OUTPUT:", response.output_text)

    return json.loads(response.output_text)
