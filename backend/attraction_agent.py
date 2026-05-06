from places_service import search_places


def get_attraction_recommendations(trip):
    destination_city = trip["destination_city"]
    traveler_type = trip["traveler_type"]
    budget = trip["budget"]
    has_car = trip["has_car"]

    # Basic query for now
    places_data = search_places(
        query="tourist attractions",
        location=destination_city
    )

    results = []

    for place in places_data["results"]:
        results.append({
            "name": place["name"],
            "address": place["address"],
            "rating": place["rating"],
            "place_id": place["place_id"],
            "reason": f"Popular attraction in {destination_city}. Suitable for {traveler_type} traveler.",
            "source_agent": "Attraction Agent",
            "source_api": "Google Places"
        })

    return {
        "agent": "Attraction Agent",
        "destination_city": destination_city,
        "recommendations": results
    }