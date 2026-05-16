from fastapi import HTTPException
from sqlalchemy import text

from ai_service import add_attraction_json


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
        SELECT name
        FROM itinerary_items
        WHERE day_id = :day_id;
    """), {"day_id": day["id"]}).fetchall()

    existing_names = [row[0] for row in existing_items]

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
        "start_time": new_item["start_time"],
        "end_time": new_item["end_time"],
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
