from fastapi import HTTPException
from sqlalchemy import text


def execute_delete_items(db, trip_id: int, action: dict):
    item_ids = action.get("item_ids") or []

    if not item_ids or not isinstance(item_ids, list):
        raise HTTPException(status_code=400, detail="No items provided for deletion")

    item_ids = list(dict.fromkeys(item_ids))

    items = db.execute(text("""
        SELECT id, name, locked
        FROM itinerary_items
        WHERE trip_id = :trip_id
          AND id = ANY(:item_ids);
    """), {
        "trip_id": trip_id,
        "item_ids": item_ids
    }).mappings().fetchall()

    if len(items) != len(item_ids):
        raise HTTPException(status_code=404, detail="One or more itinerary items were not found")

    locked_items = [dict(item) for item in items if item["locked"]]
    if locked_items:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "One or more items are locked and cannot be deleted",
                "items": locked_items
            }
        )

    db.execute(text("""
        DELETE FROM itinerary_items
        WHERE trip_id = :trip_id
          AND id = ANY(:item_ids);
    """), {
        "trip_id": trip_id,
        "item_ids": item_ids
    })

    return {
        "message": "Itinerary items deleted successfully",
        "deleted_item_ids": item_ids
    }
