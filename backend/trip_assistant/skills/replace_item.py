from fastapi import HTTPException
from sqlalchemy import text

from ai_service import replace_itinerary_item_json


def execute_replace_item(db, trip_id: int, action: dict):
    item_id = action.get("item_id")

    if not item_id:
        raise HTTPException(status_code=400, detail="No item provided for replacement")

    current_item = db.execute(text("""
        SELECT *
        FROM itinerary_items
        WHERE id = :item_id
          AND trip_id = :trip_id;
    """), {
        "item_id": item_id,
        "trip_id": trip_id
    }).mappings().fetchone()

    if not current_item:
        raise HTTPException(status_code=404, detail="Itinerary item not found")

    if current_item["locked"]:
        raise HTTPException(status_code=400, detail="This item is locked and cannot be replaced")

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": trip_id}).mappings().fetchone()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    existing_items = db.execute(text("""
        SELECT name
        FROM itinerary_items
        WHERE day_id = :day_id
          AND id != :item_id;
    """), {
        "day_id": current_item["day_id"],
        "item_id": item_id
    }).fetchall()

    existing_names = [row[0] for row in existing_items]
    preference = action.get("preference") or ""

    new_item = replace_itinerary_item_json(
        dict(trip),
        dict(current_item),
        existing_names,
        replacement_preference=preference
    )

    # Replacing a card should not silently reschedule the day. Time changes are
    # handled by the schedule-conflict LangGraph workflow.
    replacement_start_time = str(current_item["start_time"])[:5]
    replacement_end_time = str(current_item["end_time"])[:5]

    updated_item = db.execute(text("""
        UPDATE itinerary_items
        SET
            item_type = :item_type,
            start_time = :start_time,
            end_time = :end_time,
            name = :name,
            address = :address,
            notes = :notes,
            source_agent = :source_agent,
            source_api = :source_api,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = :item_id
        RETURNING *;
    """), {
        "item_id": item_id,
        "item_type": new_item["item_type"],
        "start_time": replacement_start_time,
        "end_time": replacement_end_time,
        "name": new_item["name"],
        "address": new_item["address"],
        "notes": new_item["notes"],
        "source_agent": new_item["source_agent"],
        "source_api": new_item["source_api"]
    }).mappings().fetchone()

    return {
        "message": "Itinerary item replaced successfully",
        "item": dict(updated_item)
    }
