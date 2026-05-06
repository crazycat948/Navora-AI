import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from places_service import search_places

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_food_recommendations(trip):
    destination_city = trip["destination_city"]
    traveler_type = trip["traveler_type"]
    budget = trip["budget"]
    has_car = trip["has_car"]

    places_data = search_places(
        query="restaurants",
        location=destination_city
    )

    prompt = f"""
You are the Food Agent for an AI Travel Planner.

Your job is to recommend restaurants based on the user's trip profile.

Trip information:
- Destination city: {destination_city}
- Traveler type: {traveler_type}
- Budget: {budget}
- Has car: {has_car}

Google Places candidate restaurants:
{json.dumps(places_data["results"], indent=2)}

Choose the best restaurants from the candidates.

Return ONLY valid JSON with this structure:

{{
  "agent": "Food Agent",
  "destination_city": "{destination_city}",
  "recommendations": [
    {{
      "name": "string",
      "address": "string",
      "rating": 4.7,
      "place_id": "string",
      "reason": "string",
      "meal_type": "breakfast / lunch / dinner / snack",
      "estimated_duration_hours": 1,
      "best_time_to_visit": "morning / afternoon / evening",
      "source_agent": "Food Agent",
      "source_api": "Google Places + OpenAI"
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

    print("FOOD AGENT RAW OUTPUT:", response.output_text)

    return json.loads(response.output_text)