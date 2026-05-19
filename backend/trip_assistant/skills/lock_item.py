from fastapi import HTTPException
from sqlalchemy import text


def execute_lock_item(db, trip_id: int, action: dict, locked: bool):
    item_id = action.get("item_id")

    if not item_id:
        raise HTTPException(status_code=400, detail="No item provided")

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

    updated_item = db.execute(text("""
        UPDATE itinerary_items
        SET locked = :locked,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = :item_id
          AND trip_id = :trip_id
        RETURNING *;
    """), {
        "item_id": item_id,
        "trip_id": trip_id,
        "locked": locked
    }).mappings().fetchone()

    return {
        "message": "Itinerary item locked successfully" if locked else "Itinerary item unlocked successfully",
        "item": dict(updated_item)
    }
