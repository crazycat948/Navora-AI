import re

from fastapi import HTTPException
from sqlalchemy import text


def validate_hhmm(value: str):
    if not isinstance(value, str) or not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", value):
        raise HTTPException(status_code=400, detail="Time must be in HH:MM format")


def time_to_minutes(value):
    time_text = str(value)[:5]
    validate_hhmm(time_text)
    hours, minutes = time_text.split(":")
    return int(hours) * 60 + int(minutes)


def execute_edit_item_time(db, trip_id: int, action: dict):
    item_id = action.get("item_id")
    start_time = action.get("start_time")
    end_time = action.get("end_time")

    validate_hhmm(start_time)
    validate_hhmm(end_time)

    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)

    if start_minutes >= end_minutes:
        raise HTTPException(status_code=400, detail="Start time must be before end time")

    item = db.execute(text("""
        SELECT *
        FROM itinerary_items
        WHERE id = :item_id
          AND trip_id = :trip_id;
    """), {
        "item_id": item_id,
        "trip_id": trip_id
    }).mappings().fetchone()

    if not item:
        raise HTTPException(status_code=404, detail="Itinerary item not found")

    if item["locked"]:
        raise HTTPException(status_code=400, detail="This item is locked and cannot be edited")

    same_day_items = db.execute(text("""
        SELECT id, name, start_time, end_time
        FROM itinerary_items
        WHERE day_id = :day_id
          AND id != :item_id;
    """), {
        "day_id": item["day_id"],
        "item_id": item_id
    }).mappings().fetchall()

    conflicts = []
    for existing in same_day_items:
        existing_start = time_to_minutes(existing["start_time"])
        existing_end = time_to_minutes(existing["end_time"])
        if start_minutes < existing_end and end_minutes > existing_start:
            conflicts.append({
                "id": existing["id"],
                "name": existing["name"],
                "start_time": str(existing["start_time"])[:5],
                "end_time": str(existing["end_time"])[:5]
            })

    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This time conflicts with another item on the same day",
                "conflicts": conflicts
            }
        )

    updated_item = db.execute(text("""
        UPDATE itinerary_items
        SET start_time = :start_time,
            end_time = :end_time,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = :item_id
        RETURNING *;
    """), {
        "item_id": item_id,
        "start_time": start_time,
        "end_time": end_time
    }).mappings().fetchone()

    return {
        "message": "Itinerary item time updated successfully",
        "item": dict(updated_item)
    }
