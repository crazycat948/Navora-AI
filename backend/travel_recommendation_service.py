import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_hotel_flight_recommendations(trip):
    prompt = f"""
You are a travel logistics recommendation agent.

Generate hotel and flight recommendations for this trip.

Trip:
- Departure city: {trip["departure_city"]}
- Destination city: {trip["destination_city"]}
- Arrival date: {trip["arrival_date"]}
- Departure date: {trip["departure_date"]}
- Budget: {trip["budget"]}
- Need hotel: {trip["need_hotel"]}
- Need flight: {trip["need_flight"]}

Return ONLY valid JSON:

{{
  "hotels": [
    {{
      "hotel_name": "string",
      "address": "string",
      "price_estimate": 200,
      "rating": 4.5,
      "notes": "string",
      "source_api": "OpenAI",
      "external_hotel_id": null
    }}
  ],
  "flights": [
    {{
      "airline": "string",
      "departure_airport": "string",
      "arrival_airport": "string",
      "departure_time": "YYYY-MM-DD HH:MM:SS",
      "arrival_time": "YYYY-MM-DD HH:MM:SS",
      "price_estimate": 300,
      "notes": "string",
      "source_api": "OpenAI"
    }}
  ]
}}

Rules:
- If need_hotel is false, return "hotels": [].
- If need_flight is false, return "flights": [].
- Generate 3 hotel recommendations if needed.
- Generate 2 flight recommendations if needed.
- Use realistic airport codes when possible.
- Do not include markdown or explanation.
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )

    print("HOTEL FLIGHT RAW OUTPUT:", response.output_text)

    return json.loads(response.output_text)