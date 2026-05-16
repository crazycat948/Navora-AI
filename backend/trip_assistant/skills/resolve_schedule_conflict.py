from fastapi import HTTPException
from sqlalchemy import text

from trip_assistant.skills.add_user_place import execute_add_user_place
from trip_assistant.skills.edit_item_time import time_to_minutes, validate_hhmm


def _validate_range(start_time, end_time):
    validate_hhmm(start_time)
    validate_hhmm(end_time)
    if time_to_minutes(start_time) >= time_to_minutes(end_time):
        raise HTTPException(status_code=400, detail="Start time must be before end time")


def _overlaps(start_time, end_time, items, ignore_ids=None):
    ignore_ids = set(ignore_ids or [])
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)

    for item in items:
        if item["id"] in ignore_ids:
            continue
        existing_start = time_to_minutes(item["start_time"])
        existing_end = time_to_minutes(item["end_time"])
        if start_minutes < existing_end and end_minutes > existing_start:
            return True

    return False


def execute_resolve_schedule_conflict(db, trip_id: int, action: dict):
    fixed_change = action.get("fixed_change") or {}
    proposed_moves = action.get("proposed_moves") or []
    pending_add = action.get("pending_add")

    if not fixed_change or not proposed_moves:
        raise HTTPException(status_code=400, detail="No conflict resolution plan provided")

    fixed_item_id = fixed_change.get("item_id")
    fixed_start = fixed_change.get("start_time")
    fixed_end = fixed_change.get("end_time")
    _validate_range(fixed_start, fixed_end)

    if pending_add:
        day = db.execute(text("""
            SELECT *
            FROM itinerary_days
            WHERE trip_id = :trip_id
              AND day_number = :day_number;
        """), {
            "trip_id": trip_id,
            "day_number": pending_add.get("day_number")
        }).mappings().fetchone()

        if not day:
            raise HTTPException(status_code=404, detail="Day not found")

        fixed_item = {
            "id": None,
            "name": pending_add.get("place_name") or "new place",
            "day_id": day["id"],
            "locked": False
        }
    else:
        fixed_item = db.execute(text("""
            SELECT *
            FROM itinerary_items
            WHERE id = :item_id
              AND trip_id = :trip_id;
        """), {
            "item_id": fixed_item_id,
            "trip_id": trip_id
        }).mappings().fetchone()

        if not fixed_item:
            raise HTTPException(status_code=404, detail="Target item not found")

        if fixed_item["locked"]:
            raise HTTPException(status_code=400, detail="Target item is locked and cannot be edited")

    same_day_items = db.execute(text("""
        SELECT id, name, start_time, end_time, locked
        FROM itinerary_items
        WHERE day_id = :day_id;
    """), {"day_id": fixed_item["day_id"]}).mappings().fetchall()
    same_day_items = [dict(item) for item in same_day_items]

    move_by_id = {}
    for move in proposed_moves:
        item_id = move.get("item_id")
        start_time = move.get("start_time")
        end_time = move.get("end_time")
        _validate_range(start_time, end_time)
        move_by_id[item_id] = {
            "start_time": start_time,
            "end_time": end_time
        }

    moving_ids = set(move_by_id.keys())
    if fixed_item_id is not None:
        moving_ids.add(fixed_item_id)

    for item in same_day_items:
        if item["id"] in move_by_id and item["locked"]:
            raise HTTPException(
                status_code=400,
                detail=f"Item #{item['id']} is locked and cannot be moved"
            )

    simulated_items = []

    for item in same_day_items:
        if item["id"] not in moving_ids:
            simulated_items.append(item)

    if _overlaps(fixed_start, fixed_end, simulated_items):
        raise HTTPException(status_code=409, detail="Fixed target time still conflicts with the schedule")

    simulated_items.append({
        "id": fixed_item_id,
        "name": fixed_item["name"],
        "start_time": fixed_start,
        "end_time": fixed_end
    })

    for item_id, move in move_by_id.items():
        if _overlaps(move["start_time"], move["end_time"], simulated_items):
            raise HTTPException(status_code=409, detail="Proposed conflict resolution still overlaps")
        simulated_items.append({
            "id": item_id,
            "name": f"item {item_id}",
            "start_time": move["start_time"],
            "end_time": move["end_time"]
        })

    updated_items = []

    if not pending_add:
        updated_fixed = db.execute(text("""
            UPDATE itinerary_items
            SET start_time = :start_time,
                end_time = :end_time,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :item_id
              AND trip_id = :trip_id
            RETURNING *;
        """), {
            "item_id": fixed_item_id,
            "trip_id": trip_id,
            "start_time": fixed_start,
            "end_time": fixed_end
        }).mappings().fetchone()
        updated_items.append(dict(updated_fixed))

    for item_id, move in move_by_id.items():
        updated_move = db.execute(text("""
            UPDATE itinerary_items
            SET start_time = :start_time,
                end_time = :end_time,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :item_id
              AND trip_id = :trip_id
            RETURNING *;
        """), {
            "item_id": item_id,
            "trip_id": trip_id,
            "start_time": move["start_time"],
            "end_time": move["end_time"]
        }).mappings().fetchone()

        if not updated_move:
            raise HTTPException(status_code=404, detail=f"Item #{item_id} not found")

        updated_items.append(dict(updated_move))

    if pending_add:
        pending_add["start_time"] = fixed_start
        pending_add["end_time"] = fixed_end
        add_result = execute_add_user_place(db, trip_id, pending_add)
        updated_items.append(add_result["item"])

    return {
        "message": "Schedule conflict resolved successfully",
        "items": updated_items
    }
