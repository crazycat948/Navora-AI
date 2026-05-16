import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def test_openai_connection():
    response = client.responses.create(
        model=OPENAI_MODEL,
        input="Say: OpenAI connected successfully."
    )
    return response.output_text


def generate_itinerary_json(trip, attraction_data=None, food_data=None, weather_data=None):
    prompt = f"""
You are the Itinerary Planner Agent for an AI Travel Planner.

Your job is to create a realistic, structured, day-by-day itinerary using ONLY the agent-provided data.

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

Attraction Agent recommendations:
{json.dumps(attraction_data, indent=2) if attraction_data else "None"}

Food Agent recommendations:
{json.dumps(food_data, indent=2) if food_data else "None"}

Weather Agent recommendations:
{json.dumps(weather_data, indent=2) if weather_data else "None"}

STRICT PLANNING RULES:
- For attraction items, ONLY use places from Attraction Agent recommendations.
- For restaurant items, ONLY use places from Food Agent recommendations.
- NEVER invent attraction names.
- NEVER invent restaurant names.
- NEVER create vague activities like "Explore the beach", "Walk around downtown", or "Shopping time" unless they are provided by an agent.
- Every attraction item MUST include the exact place_id from Attraction Agent as external_place_id.
- Every restaurant item MUST include the exact place_id from Food Agent as external_place_id.
- Do NOT repeat the same place more than once in the entire itinerary.
- Use the exact name and address from the agent recommendation.
- Use Weather Agent advice to decide indoor/outdoor activity timing.
- If weather is sunny, outdoor attractions are preferred.
- If weather is rainy, indoor attractions and restaurants are preferred.
- Keep the schedule realistic.
- Restaurants: always include exactly 2 restaurant items per day (1 lunch + 1 dinner), regardless of traveler type.
- Attractions per day are determined by traveler type:
  - "speedrunning": 4 attractions per day — 2 in the morning, 2 in the afternoon
  - "normal": 2 attractions per day — 1 in the morning, 1 in the afternoon
  - "chill": 1 attraction per day — scheduled in the afternoon only
- Lunch should usually be around 12:00-14:00.
- Dinner should usually be around 17:30-20:00.
- Morning attractions should be scheduled before lunch (before 12:00).
- Afternoon attractions should be scheduled after lunch and before dinner (14:00-17:00).

IMPORTANT:
If there are not enough unique agent-provided places for every day, create fewer items instead of inventing new places.

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
          "source_api": "Google Places or Google Places + OpenAI",
          "external_place_id": "string"
        }}
      ]
    }}
  ]
}}

Return ONLY valid JSON.
Do NOT include markdown.
Do NOT include explanations.
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    print("ITINERARY RAW OUTPUT:", response.output_text)

    return json.loads(response.output_text)


def replace_itinerary_item_json(trip, current_item, existing_names, replacement_preference=None):
    existing_list = "\n".join(f"- {name}" for name in existing_names) if existing_names else "None"
    preference_text = replacement_preference or "No extra preference provided."

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

User replacement preference:
{preference_text}

Existing places already in the itinerary:
{existing_list}

Do NOT recommend any place that appears above. Avoid duplicates.

Generate ONE replacement item with the same item_type and similar time duration.
Honor the user replacement preference when provided. Broad preferences like "cheaper restaurant", "something outdoors", or "family friendly attraction" are specific enough; do not ask follow-up questions.

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
        model=OPENAI_MODEL,
        input=prompt
    )

    print("REPLACE RAW OUTPUT:", response.output_text)

    return json.loads(response.output_text)


def add_attraction_json(trip, date, existing_names, attraction_preference=None):
    existing_list = "\n".join(f"- {name}" for name in existing_names) if existing_names else "None"
    preference_text = attraction_preference or "No extra preference provided."

    prompt = f"""
You are an AI travel planner.

The user wants to add an extra attraction to their itinerary for a specific day.

Trip information:
- Destination City: {trip["destination_city"]}
- Date: {date}
- Traveler Type: {trip["traveler_type"]}
- Budget: {trip["budget"]}
- Has Car: {trip["has_car"]}

Places already in the itinerary (do NOT repeat any of these):
{existing_list}

User attraction preference:
{preference_text}

Generate ONE new attraction for this destination. It must be a real, well-known place.
Honor the user attraction preference when provided. Broad preferences like "coffee shop", "outdoor activity", or "kid friendly place" are specific enough; do not ask follow-up questions.
Pick a time slot that does not conflict with typical meal times (12:00-14:00 for lunch, 17:30-20:00 for dinner).

Return ONLY valid JSON with this structure:

{{
  "item_type": "attraction",
  "start_time": "HH:MM",
  "end_time": "HH:MM",
  "name": "string",
  "address": "string",
  "notes": "string",
  "source_agent": "Attraction Agent",
  "source_api": "OpenAI"
}}

Do NOT include explanation, markdown, or extra text.
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    print("ADD ATTRACTION RAW OUTPUT:", response.output_text)

    return json.loads(response.output_text)
