import json
import os

from fastapi import HTTPException
from openai import OpenAI

from city_service import get_city_coordinates
from weather_service import get_hourly_weather_forecast, get_weather_forecast

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def find_day(trip_context, action):
    day_number = action.get("day_number")
    target_date = action.get("date")

    for day in trip_context["days"]:
        if day_number and day["day_number"] == day_number:
            return day
        if target_date and day["date"] == target_date:
            return day

    return None


def summarize_weather(trip_context, day, hourly_data, daily_data):
    prompt = f"""
You are the Weather Skill for Navora AI.

Use the weather API data below to answer the user's weather question for one trip day.

Rules:
- If the API data does not include the target date, say that forecast data is not available yet.
- Weather APIs often only provide reliable detail for about the next week; be honest if the date is out of range.
- If hourly data is available for the target date, summarize the day by morning, midday, afternoon, and evening.
- Mention likely changes through the day, such as cloudy morning, brief midday rain, or clearing in the afternoon.
- Keep the answer concise and useful for travel planning.
- Do not invent details that are not supported by the API data.

Trip:
{json.dumps(trip_context["trip"], indent=2, default=str)}

Target day:
{json.dumps(day, indent=2, default=str)}

Hourly weather API data:
{json.dumps(hourly_data, indent=2, default=str)}

Daily weather API data:
{json.dumps(daily_data, indent=2, default=str)}

Return only the assistant reply text.
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    return response.output_text


def execute_ask_weather(trip_context, action):
    day = find_day(trip_context, action)

    if not day:
        raise HTTPException(status_code=404, detail="Day not found")

    destination_city = trip_context["trip"]["destination_city"]
    city_location = get_city_coordinates(destination_city)

    if not city_location:
        raise HTTPException(status_code=404, detail="Could not find destination city coordinates")

    hourly_data = get_hourly_weather_forecast(
        latitude=city_location["latitude"],
        longitude=city_location["longitude"],
        hours=168
    )

    daily_data = get_weather_forecast(
        latitude=city_location["latitude"],
        longitude=city_location["longitude"],
        days=7
    )

    reply = summarize_weather(
        trip_context=trip_context,
        day=day,
        hourly_data=hourly_data,
        daily_data=daily_data
    )

    return {
        "reply": reply,
        "action": None,
        "trip_id": trip_context["trip"]["id"]
    }
