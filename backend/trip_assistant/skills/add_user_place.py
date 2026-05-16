from fastapi import HTTPException
from sqlalchemy import text

from trip_assistant.skills.destination_guard import validate_destination_place


def time_to_minutes(value):
    time_text = str(value)[:5]
    hours, minutes = time_text.split(":")
    return int(hours) * 60 + int(minutes)


def overlaps(start_time, end_time, existing_items):
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)

    for item in existing_items:
        existing_start = time_to_minutes(item["start_time"])
        existing_end = time_to_minutes(item["end_time"])
        if start_minutes < existing_end and end_minutes > existing_start:
            return True

    return False


def find_open_slot(item_type, existing_items):
    restaurant_slots = [
        ("12:00", "13:00"),
        ("13:00", "14:00"),
        ("18:00", "19:00"),
        ("19:00", "20:00")
    ]

    attraction_slots = [
        ("09:00", "11:00"),
        ("10:00", "12:00"),
        ("14:00", "16:00"),
        ("16:00", "18:00")
    ]

    slots = restaurant_slots if item_type == "restaurant" else attraction_slots

    for start_time, end_time in slots:
        if not overlaps(start_time, end_time, existing_items):
            return start_time, end_time

    raise HTTPException(
        status_code=409,
        detail="Could not find an open time slot for this place on the selected day"
    )


def normalize_item_type(value):
    return "restaurant" if value == "restaurant" else "attraction"


def execute_add_user_place(db, trip_id: int, action: dict):
    day_number = action.get("day_number")
    place_name = (action.get("place_name") or "").strip()
    item_type = normalize_item_type(action.get("item_type"))

    if not day_number:
        raise HTTPException(status_code=400, detail="No day provided for the new place")

    if not place_name:
        raise HTTPException(status_code=400, detail="No place name provided")

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": trip_id}).mappings().fetchone()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    day = db.execute(text("""
        SELECT *
        FROM itinerary_days
        WHERE trip_id = :trip_id
          AND day_number = :day_number;
    """), {
        "trip_id": trip_id,
        "day_number": day_number
    }).mappings().fetchone()

    if not day:
        raise HTTPException(status_code=404, detail="Day not found")

    existing_items = db.execute(text("""
        SELECT id, name, start_time, end_time
        FROM itinerary_items
        WHERE day_id = :day_id;
    """), {"day_id": day["id"]}).mappings().fetchall()

    existing_names = [item["name"].lower() for item in existing_items]
    if place_name.lower() in existing_names:
        raise HTTPException(status_code=400, detail="This place is already in the selected day")

    place = action.get("validated_place")
    if not place:
        guard_result = validate_destination_place(
            place_name=place_name,
            destination_city=trip["destination_city"],
            has_car=trip["has_car"]
        )

        if guard_result["status"] == "blocked":
            raise HTTPException(status_code=400, detail=guard_result["message"])

        place = guard_result["place"]

    if action.get("start_time") and action.get("end_time"):
        start_time = action["start_time"]
        end_time = action["end_time"]
        if overlaps(start_time, end_time, existing_items):
            raise HTTPException(status_code=409, detail="This requested time conflicts with another item")
    else:
        start_time, end_time = find_open_slot(item_type, existing_items)

    max_order = db.execute(text("""
        SELECT COALESCE(MAX(order_index), 0)
        FROM itinerary_items
        WHERE day_id = :day_id;
    """), {"day_id": day["id"]}).scalar()

    inserted = db.execute(text("""
        INSERT INTO itinerary_items (
            trip_id, day_id, item_type, start_time, end_time,
            name, address, notes, source_agent, source_api, external_place_id, order_index
        )
        VALUES (
            :trip_id, :day_id, :item_type, :start_time, :end_time,
            :name, :address, :notes, :source_agent, :source_api, :external_place_id, :order_index
        )
        RETURNING *;
    """), {
        "trip_id": trip_id,
        "day_id": day["id"],
        "item_type": item_type,
        "start_time": start_time,
        "end_time": end_time,
        "name": place["name"] or place_name,
        "address": place["address"],
        "notes": "User-provided place added through the trip assistant.",
        "source_agent": "User + Google Places",
        "source_api": "Google Places",
        "external_place_id": place["place_id"],
        "order_index": max_order + 1
    }).mappings().fetchone()

    return {
        "message": "User-provided place added successfully",
        "item": dict(inserted),
        "day_number": day["day_number"]
    }
