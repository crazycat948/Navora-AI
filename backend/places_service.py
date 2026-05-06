import os
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


def search_places(query, location):
    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.id"
    }

    body = {
        "textQuery": f"{query} in {location}",
        "maxResultCount": 5
    }

    response = requests.post(url, headers=headers, json=body)
    data = response.json()

    print("GOOGLE NEW PLACES RAW RESPONSE:", data)

    results = []

    for place in data.get("places", []):
        results.append({
            "place_id": place.get("id"),
            "name": place.get("displayName", {}).get("text"),
            "address": place.get("formattedAddress"),
            "rating": place.get("rating")
        })

    return {
        "results": results
    }