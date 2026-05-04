import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def test_openai_connection():
    response = client.responses.create(
        model="gpt-4o-mini",
        input="Say: OpenAI connected successfully."
    )
    return response.output_text


def generate_itinerary_json(trip):
    prompt = f"""
You are an AI travel planner.

Generate a structured one-day travel itinerary in JSON format.

Trip information:
- Title: {trip["title"]}
- Destination City: {trip["destination_city"]}
- Departure City: {trip["departure_city"]}
- Arrival Date: {trip["arrival_date"]}
- Departure Date: {trip["departure_date"]}
- Traveler Type: {trip["traveler_type"]}
- Budget: {trip["budget"]}
- Has Car: {trip["has_car"]}
- Need Hotel: {trip["need_hotel"]}
- Need Flight: {trip["need_flight"]}

Return ONLY valid JSON with this structure:

{{
  "days": [
    {{
      "date": "YYYY-MM-DD",
      "day_number": 1,
      "theme": "string",
      "notes": "string",
      "items": [
        {{
          "item_type": "attraction or restaurant",
          "start_time": "HH:MM",
          "end_time": "HH:MM",
          "name": "string",
          "address": "string",
          "notes": "string",
          "source_agent": "Attraction Agent or Food Agent",
          "source_api": "OpenAI"
        }}
      ]
    }}
  ]
}}

Return ONLY valid JSON. Do NOT include any explanation, text, or markdown.
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )

    return json.loads(response.output_text)


def replace_itinerary_item_json(trip, current_item, existing_names):
    existing_list = "\n".join(f"- {name}" for name in existing_names) if existing_names else "None"

    prompt = f"""
You are an AI travel planner.

The user wants to replace one itinerary item.

Trip information:
- Destination City: {trip["destination_city"]}
- Arrival Date: {trip["arrival_date"]}
- Departure Date: {trip["departure_date"]}
- Traveler Type: {trip["traveler_type"]}
- Budget: {trip["budget"]}
- Has Car: {trip["has_car"]}

Current item to replace:
- Type: {current_item["item_type"]}
- Name: {current_item["name"]}
- Address: {current_item["address"]}
- Time: {current_item["start_time"]} to {current_item["end_time"]}
- Notes: {current_item["notes"]}

Existing places already in the itinerary:
{existing_list}

Do NOT recommend any place that appears above. Avoid duplicates.

Generate ONE replacement item with the same item_type and similar time duration.

Return ONLY valid JSON with this structure:

{{
  "item_type": "attraction or restaurant",
  "start_time": "HH:MM",
  "end_time": "HH:MM",
  "name": "string",
  "address": "string",
  "notes": "string",
  "source_agent": "Attraction Agent or Food Agent",
  "source_api": "OpenAI"
}}

Do NOT include explanation, markdown, or extra text.
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )

    print("REPLACE RAW OUTPUT:", response.output_text)

    return json.loads(response.output_text)