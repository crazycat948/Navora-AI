import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from weather_service import get_weather_forecast

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_weather_recommendations(trip):
    destination_city = trip["destination_city"]

    # Temporary hardcoded LA coordinates
    latitude = 34.0522
    longitude = -118.2437

    weather_data = get_weather_forecast(
        latitude=latitude,
        longitude=longitude,
        days=5
    )

    prompt = f"""
You are the Weather Agent for an AI Travel Planner.

Analyze the weather forecast and provide travel planning recommendations.

Destination city:
{destination_city}

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