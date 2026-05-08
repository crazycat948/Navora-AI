import os
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


def search_cities(query: str):
    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress"
    }

    body = {
        "textQuery": query,
        "includedType": "locality",
        "maxResultCount": 5,
        "languageCode": "en"
    }

    response = requests.post(url, headers=headers, json=body)
    data = response.json()

    cities = []
    for place in data.get("places", []):
        name = place.get("displayName", {}).get("text", "")
        address = place.get("formattedAddress", "")
        cities.append({
            "name": name,
            "label": f"{name}, {address}" if address else name
        })

    return cities
