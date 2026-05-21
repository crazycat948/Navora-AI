HELP_TOPICS = {
    "general": (
        "Navora AI helps you create and edit AI-generated travel itineraries. "
        "Start by creating a trip with your destination, dates, pace, budget, and travel options. "
        "After the itinerary is generated, open the trip detail page to review each day, edit cards, "
        "add attractions, check weather, and use the Trip Assistant chatbox for guided changes."
    ),
    "create_trip": (
        "To create a trip, fill in the trip form with a title, departure city, destination city, "
        "arrival/departure dates, traveler type, budget, and options like car, hotel, or flight. "
        "Submit the form and Navora will generate a day-by-day itinerary."
    ),
    "trip_detail": (
        "The trip detail page shows your itinerary grouped by day. Each card has a type, place name, "
        "time range, address, notes, and action buttons. You can edit times and notes, lock important "
        "cards, delete cards, replace cards, or add more attractions."
    ),
    "edit_cards": (
        "Use Save after changing a card's start time, end time, or notes. Delete removes an unlocked card. "
        "Lock protects a card from edits, replacement, movement, and deletion. Unlock makes it editable again. "
        "Replace swaps an unlocked card for a new AI-generated alternative."
    ),
    "chatbox": (
        "Open the Trip Assistant chatbox from the trip detail page. It is connected to the current trip, "
        "so you can reference visible days and item IDs. For changes, it proposes an action first and asks "
        "you to confirm before saving anything."
    ),
    "chatbox_skills": (
        "The Trip Assistant can edit item times, move items to another day, delete items, lock or unlock items, "
        "replace places, add generated attractions, add specific places after Google Places validation, find free "
        "time slots, insert attractions into open slots, explain proposed schedule conflicts, and answer weather questions."
    ),
    "weather": (
        "Ask the Trip Assistant about weather for a specific trip day, such as 'what is the weather on day 2?' "
        "It will summarize available forecast data. Weather APIs may not have reliable details for dates far in the future."
    ),
    "account": (
        "Log in before creating or managing trips. Trip-specific chat and editing actions use your logged-in account "
        "so the backend can verify that the trip belongs to you."
    )
}


def normalize_topic(topic):
    topic = (topic or "general").strip().lower()
    aliases = {
        "create": "create_trip",
        "create trip": "create_trip",
        "new trip": "create_trip",
        "trip": "trip_detail",
        "trip detail": "trip_detail",
        "cards": "edit_cards",
        "card": "edit_cards",
        "edit": "edit_cards",
        "buttons": "edit_cards",
        "assistant": "chatbox",
        "chat": "chatbox",
        "chatbox": "chatbox",
        "skills": "chatbox_skills",
        "chatbox skills": "chatbox_skills",
        "weather": "weather",
        "login": "account",
        "account": "account"
    }
    return aliases.get(topic, topic if topic in HELP_TOPICS else "general")


def execute_app_help(trip_context, action):
    topic = normalize_topic(action.get("topic"))

    return {
        "reply": HELP_TOPICS[topic],
        "action": None,
        "trip_id": trip_context["trip"]["id"],
        "topic": topic
    }
