from fastapi import HTTPException
from sqlalchemy import text

from ai_service import add_attraction_json
from trip_assistant.skills.edit_item_time import time_to_minutes, validate_hhmm


def _overlaps(start_time, end_time, existing_items):
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)

    for item in existing_items:
        existing_start = time_to_minutes(item["start_time"])
        existing_end = time_to_minutes(item["end_time"])
        if start_minutes < existing_end and end_minutes > existing_start:
            return item

    return None


def execute_add_attraction(db, trip_id: int, action: dict):
    day_number = action.get("day_number")

    if not day_number:
        raise HTTPException(status_code=400, detail="No day provided for the new attraction")

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

    existing_names = [item["name"] for item in existing_items]

    max_order = db.execute(text("""
        SELECT COALESCE(MAX(order_index), 0)
        FROM itinerary_items
        WHERE day_id = :day_id;
    """), {"day_id": day["id"]}).scalar()

    new_item = add_attraction_json(
        dict(trip),
        str(day["date"]),
        existing_names,
        attraction_preference=action.get("preference") or ""
    )

    start_time = action.get("start_time") or new_item["start_time"]
    end_time = action.get("end_time") or new_item["end_time"]
    validate_hhmm(start_time)
    validate_hhmm(end_time)

    if time_to_minutes(start_time) >= time_to_minutes(end_time):
        raise HTTPException(status_code=400, detail="Start time must be before end time")

    conflict = _overlaps(start_time, end_time, existing_items)
    if conflict:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This attraction time conflicts with another item on the same day",
                "conflicts": [{
                    "id": conflict["id"],
                    "name": conflict["name"],
                    "start_time": str(conflict["start_time"])[:5],
                    "end_time": str(conflict["end_time"])[:5]
                }]
            }
        )

    inserted = db.execute(text("""
        INSERT INTO itinerary_items (
            trip_id, day_id, item_type, start_time, end_time,
            name, address, notes, source_agent, source_api, order_index
        )
        VALUES (
            :trip_id, :day_id, :item_type, :start_time, :end_time,
            :name, :address, :notes, :source_agent, :source_api, :order_index
        )
        RETURNING *;
    """), {
        "trip_id": trip_id,
        "day_id": day["id"],
        "item_type": new_item["item_type"],
        "start_time": start_time,
        "end_time": end_time,
        "name": new_item["name"],
        "address": new_item["address"],
        "notes": new_item["notes"],
        "source_agent": new_item["source_agent"],
        "source_api": new_item["source_api"],
        "order_index": max_order + 1
    }).mappings().fetchone()

    return {
        "message": "Attraction added successfully",
        "item": dict(inserted),
        "day_number": day["day_number"]
    }
