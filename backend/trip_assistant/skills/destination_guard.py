from places_service import search_places


GENERIC_PLACE_WORDS = {
    "a", "an", "the", "something", "place", "attraction", "activity",
    "restaurant", "food", "coffee", "shop", "cafe", "museum", "park",
    "beach", "outdoor", "indoor", "kid", "kids", "friendly", "tour"
}


PLACE_ALIASES = {
    "caltech": "California Institute of Technology",
    "caltech tour": "California Institute of Technology",
    "ucla": "University of California Los Angeles",
    "ucla tour": "University of California Los Angeles",
    "crypto center": "Crypto.com Arena",
    "crypto arena": "Crypto.com Arena",
    "cryptocom arena": "Crypto.com Arena",
    "staples center": "Crypto.com Arena"
}


ALLOWED_METRO_AREAS = {
    "los angeles": [
        "los angeles",
        "santa monica",
        "venice",
        "beverly hills",
        "pasadena",
        "hollywood",
        "long beach",
        "malibu",
        "anaheim",
        "burbank",
        "glendale",
        "culver city",
        "west hollywood"
    ],
    "dallas": [
        "dallas",
        "fort worth",
        "arlington",
        "plano",
        "irving",
        "frisco",
        "grapevine",
        "richardson",
        "garland"
    ]
}


def significant_tokens(text):
    tokens = []
    for raw_token in (text or "").lower().replace("-", " ").split():
        token = "".join(char for char in raw_token if char.isalnum())
        if token and token not in GENERIC_PLACE_WORDS:
            tokens.append(token)
    return tokens


def normalize_place_query(place_name):
    key = (place_name or "").lower().replace(".", "").strip()
    return PLACE_ALIASES.get(key, place_name)


def place_matches_query(place_name, place, search_query=None):
    tokens = significant_tokens(place_name)
    normalized_tokens = significant_tokens(search_query)

    if normalized_tokens and normalized_tokens != tokens:
        tokens = normalized_tokens

    if not tokens:
        return False

    haystack = f"{place.get('name') or ''} {place.get('address') or ''}".lower()
    matched = sum(1 for token in tokens if token in haystack)
    return matched / len(tokens) >= 0.6


def get_allowed_areas(destination_city):
    destination_key = (destination_city or "").lower()
    return ALLOWED_METRO_AREAS.get(destination_key, [destination_key])


def address_is_in_allowed_area(address, allowed_areas):
    address_text = (address or "").lower()
    return any(area in address_text for area in allowed_areas)


def address_specificity_score(address):
    address_text = (address or "").lower()
    score = 0

    if any(char.isdigit() for char in address_text):
        score += 2

    street_words = [
        "street", "st",
        "avenue", "ave",
        "boulevard", "blvd",
        "road", "rd",
        "drive", "dr",
        "way",
        "lane", "ln",
        "court", "ct"
    ]
    if any(word in address_text.replace(".", "").split() for word in street_words):
        score += 3

    score += min(address_text.count(","), 3)
    return score


def choose_best_place(places, place_name, search_query, allowed_areas):
    candidates = []

    for index, place in enumerate(places):
        address = place.get("address") or ""
        if not place_matches_query(place_name, place, search_query):
            continue
        if not address_is_in_allowed_area(address, allowed_areas):
            continue

        candidates.append((
            address_specificity_score(address),
            -index,
            place
        ))

    if not candidates:
        return places[0]

    candidates.sort(reverse=True)
    return candidates[0][2]


def validate_destination_place(place_name, destination_city, has_car=False):
    place_name = (place_name or "").strip()
    search_query = normalize_place_query(place_name)

    if not place_name:
        return {
            "status": "blocked",
            "message": "Please tell me the place name you want to add.",
            "place": None
        }

    places = search_places(search_query, destination_city).get("results", [])

    if not places:
        return {
            "status": "blocked",
            "message": f"I could not validate {place_name} near {destination_city}, so I cannot add it to this trip yet.",
            "place": None
        }

    allowed_areas = get_allowed_areas(destination_city)
    place = choose_best_place(places, place_name, search_query, allowed_areas)
    address = place.get("address") or ""

    if address_specificity_score(address) < 5 and address_is_in_allowed_area(address, allowed_areas):
        address_places = search_places(f"{search_query} address", destination_city).get("results", [])
        if address_places:
            address_place = choose_best_place(address_places, place_name, search_query, allowed_areas)
            address = address_place.get("address") or ""
            if address_specificity_score(address) > address_specificity_score(place.get("address") or ""):
                place = address_place

    if not place_matches_query(place_name, place, search_query):
        return {
            "status": "blocked",
            "message": (
                f"I could not validate {place_name} as a specific place near {destination_city}. "
                "I will not add a random local attraction instead."
            ),
            "place": place
        }

    if not any(area in address.lower() for area in allowed_areas):
        return {
            "status": "blocked",
            "message": (
                f"{place.get('name') or place_name} appears to be outside {destination_city} "
                f"({address or 'address unavailable'}). I will not add it to this plan automatically."
            ),
            "place": place
        }

    return {
        "status": "allowed",
        "message": "",
        "place": place
    }
