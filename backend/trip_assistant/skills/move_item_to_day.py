from fastapi import HTTPException
from sqlalchemy import text

from trip_assistant.skills.edit_item_time import time_to_minutes, validate_hhmm


DAY_START = "08:00"
DAY_END = "21:00"


def _minutes_to_hhmm(minutes):
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def _find_day(trip_context, day_number=None, target_date=None):
    for day in trip_context["days"]:
        if day_number and day["day_number"] == day_number:
            return day
        if target_date and day["date"] == target_date:
            return day

    return None


def _find_item_day(trip_context, item_id):
    for day in trip_context["days"]:
        for item in day["items"]:
            if item["id"] == item_id:
                return day, item

    return None, None


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
            return item

    return None


def _first_open_slot(items, duration_minutes, ignore_ids=None):
    ignore_ids = set(ignore_ids or [])
    busy_ranges = []
    day_start = time_to_minutes(DAY_START)
    day_end = time_to_minutes(DAY_END)

    for item in items:
        if item["id"] in ignore_ids:
            continue
        start = max(day_start, time_to_minutes(item["start_time"]))
        end = min(day_end, time_to_minutes(item["end_time"]))
        if start < end:
            busy_ranges.append((start, end))

    busy_ranges.sort(key=lambda busy: busy[0])
    cursor = day_start

    for start, end in busy_ranges:
        if start - cursor >= duration_minutes:
            return _minutes_to_hhmm(cursor), _minutes_to_hhmm(cursor + duration_minutes)
        cursor = max(cursor, end)

    if day_end - cursor >= duration_minutes:
        return _minutes_to_hhmm(cursor), _minutes_to_hhmm(cursor + duration_minutes)

    return None, None


def prepare_move_item_to_day(trip_context, chat_result):
    action = chat_result.get("action")

    if not action or action.get("type") != "move_item_to_day":
        return chat_result

    item_id = action.get("item_id")
    target_day = _find_day(
        trip_context,
        day_number=action.get("day_number"),
        target_date=action.get("date")
    )
    current_day, item = _find_item_day(trip_context, item_id)

    if not item:
        return {
            "reply": "I could not find that item in this trip. Please reference a visible item name or ID.",
            "action": None
        }

    if not target_day:
        return {
            "reply": "I could not find that day in this trip. Please choose a visible day number.",
            "action": None
        }

    if item["locked"]:
        return {
            "reply": f"Item #{item_id} is locked, so I cannot move it unless you unlock it first.",
            "action": None
        }

    if current_day["id"] == target_day["id"]:
        return {
            "reply": f"Item #{item_id} is already on Day {target_day['day_number']}.",
            "action": None
        }

    duration = time_to_minutes(item["end_time"]) - time_to_minutes(item["start_time"])
    start_time = action.get("start_time") or ""
    end_time = action.get("end_time") or ""

    if start_time and not end_time:
        validate_hhmm(start_time)
        end_time = _minutes_to_hhmm(time_to_minutes(start_time) + duration)
    elif end_time and not start_time:
        validate_hhmm(end_time)
        start_time = _minutes_to_hhmm(time_to_minutes(end_time) - duration)
    elif start_time and end_time:
        validate_hhmm(start_time)
        validate_hhmm(end_time)
        if time_to_minutes(start_time) >= time_to_minutes(end_time):
            return {
                "reply": "That time range is invalid because the start time must be before the end time.",
                "action": None
            }
    else:
        start_time, end_time = _first_open_slot(target_day["items"], duration)

    if not start_time or not end_time:
        return {
            "reply": (
                f"I could not find an open {duration}-minute slot on Day "
                f"{target_day['day_number']} between {DAY_START} and {DAY_END}."
            ),
            "action": None
        }

    conflict = _overlaps(start_time, end_time, target_day["items"])
    if conflict:
        return {
            "reply": (
                f"Moving item #{item_id} to Day {target_day['day_number']} at "
                f"{start_time}-{end_time} would conflict with #{conflict['id']} "
                f"{conflict['name']} ({str(conflict['start_time'])[:5]}-{str(conflict['end_time'])[:5]})."
            ),
            "action": None
        }

    action["day_number"] = target_day["day_number"]
    action["day_id"] = target_day["id"]
    action["start_time"] = start_time
    action["end_time"] = end_time

    return {
        "reply": (
            f"I can move item #{item_id} {item['name']} from Day {current_day['day_number']} "
            f"to Day {target_day['day_number']} at {start_time}-{end_time}. "
            "Please confirm before I make the change."
        ),
        "action": action
    }


def execute_move_item_to_day(db, trip_id: int, action: dict):
    item_id = action.get("item_id")
    day_id = action.get("day_id")
    start_time = action.get("start_time")
    end_time = action.get("end_time")

    validate_hhmm(start_time)
    validate_hhmm(end_time)

    if time_to_minutes(start_time) >= time_to_minutes(end_time):
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
        raise HTTPException(status_code=400, detail="This item is locked and cannot be moved")

    target_day = db.execute(text("""
        SELECT *
        FROM itinerary_days
        WHERE id = :day_id
          AND trip_id = :trip_id;
    """), {
        "day_id": day_id,
        "trip_id": trip_id
    }).mappings().fetchone()

    if not target_day:
        raise HTTPException(status_code=404, detail="Target day not found")

    same_day_items = db.execute(text("""
        SELECT id, name, start_time, end_time
        FROM itinerary_items
        WHERE day_id = :day_id
          AND id != :item_id;
    """), {
        "day_id": day_id,
        "item_id": item_id
    }).mappings().fetchall()

    conflict = _overlaps(start_time, end_time, same_day_items)
    if conflict:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This move conflicts with another item on the target day",
                "conflicts": [{
                    "id": conflict["id"],
                    "name": conflict["name"],
                    "start_time": str(conflict["start_time"])[:5],
                    "end_time": str(conflict["end_time"])[:5]
                }]
            }
        )

    max_order = db.execute(text("""
        SELECT COALESCE(MAX(order_index), 0)
        FROM itinerary_items
        WHERE day_id = :day_id;
    """), {"day_id": day_id}).scalar()

    updated_item = db.execute(text("""
        UPDATE itinerary_items
        SET day_id = :day_id,
            start_time = :start_time,
            end_time = :end_time,
            order_index = :order_index,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = :item_id
          AND trip_id = :trip_id
        RETURNING *;
    """), {
        "item_id": item_id,
        "trip_id": trip_id,
        "day_id": day_id,
        "start_time": start_time,
        "end_time": end_time,
        "order_index": max_order + 1
    }).mappings().fetchone()

    return {
        "message": "Itinerary item moved successfully",
        "item": dict(updated_item),
        "day_number": target_day["day_number"]
    }
