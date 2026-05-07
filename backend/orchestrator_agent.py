from attraction_agent import get_attraction_recommendations
from food_agent import get_food_recommendations
from weather_agent import get_weather_recommendations


def run_orchestrator(trip):
    print("ORCHESTRATOR STARTED")

    attraction_data = get_attraction_recommendations(trip)
    print("ATTRACTION AGENT OUTPUT:", attraction_data)

    food_data = get_food_recommendations(trip)
    print("FOOD AGENT OUTPUT:", food_data)

    weather_data = get_weather_recommendations(trip)
    print("WEATHER AGENT OUTPUT:", weather_data)

    return {
        "orchestrator": "Orchestrator Agent",
        "trip_id": trip.get("id"),
        "destination_city": trip.get("destination_city"),
        "agent_outputs": {
            "attractions": attraction_data,
            "foods": food_data,
            "weather": weather_data
        }
    }