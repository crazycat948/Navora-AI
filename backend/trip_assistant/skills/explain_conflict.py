from fastapi import HTTPException

from trip_assistant.skills.edit_item_time import time_to_minutes, validate_hhmm


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


def _format_item(item):
    return f"#{item['id']} {item['name']} ({str(item['start_time'])[:5]}-{str(item['end_time'])[:5]})"


def _overlaps(start_time, end_time, item):
    start_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)
    existing_start = time_to_minutes(item["start_time"])
    existing_end = time_to_minutes(item["end_time"])
    return start_minutes < existing_end and end_minutes > existing_start


def _current_day_conflicts(day):
    conflicts = []
    items = day["items"]

    for left_index, left in enumerate(items):
        for right in items[left_index + 1:]:
            if _overlaps(left["start_time"], left["end_time"], right):
                conflicts.append((left, right))

    return conflicts


def _requested_range(action, item):
    start_time = action.get("start_time") or ""
    end_time = action.get("end_time") or ""
    duration = time_to_minutes(item["end_time"]) - time_to_minutes(item["start_time"])

    if start_time and not end_time:
        validate_hhmm(start_time)
        end_time = _minutes_to_hhmm(time_to_minutes(start_time) + duration)
    elif end_time and not start_time:
        validate_hhmm(end_time)
        start_time = _minutes_to_hhmm(time_to_minutes(end_time) - duration)
    elif start_time and end_time:
        validate_hhmm(start_time)
        validate_hhmm(end_time)
    else:
        start_time = str(item["start_time"])[:5]
        end_time = str(item["end_time"])[:5]

    if time_to_minutes(start_time) >= time_to_minutes(end_time):
        raise HTTPException(status_code=400, detail="Start time must be before end time")

    return start_time, end_time


def execute_explain_conflict(trip_context, action):
    item_id = action.get("item_id")

    if item_id:
        current_day, item = _find_item_day(trip_context, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Itinerary item not found")

        target_day = _find_day(
            trip_context,
            day_number=action.get("day_number"),
            target_date=action.get("date")
        ) or current_day

        start_time, end_time = _requested_range(action, item)
        conflicts = [
            other for other in target_day["items"]
            if other["id"] != item_id and _overlaps(start_time, end_time, other)
        ]

        if not conflicts:
            return {
                "reply": (
                    f"I do not see a schedule conflict for #{item_id} {item['name']} "
                    f"on Day {target_day['day_number']} at {start_time}-{end_time}."
                ),
                "action": None,
                "trip_id": trip_context["trip"]["id"],
                "conflicts": []
            }

        conflict_text = "; ".join(_format_item(conflict) for conflict in conflicts)
        return {
            "reply": (
                f"Moving or setting #{item_id} {item['name']} to "
                f"{start_time}-{end_time} on Day {target_day['day_number']} would overlap with "
                f"{conflict_text}."
            ),
            "action": None,
            "trip_id": trip_context["trip"]["id"],
            "conflicts": conflicts
        }

    day = _find_day(
        trip_context,
        day_number=action.get("day_number"),
        target_date=action.get("date")
    )

    if not day:
        raise HTTPException(status_code=404, detail="Day not found")

    conflicts = _current_day_conflicts(day)
    if not conflicts:
        return {
            "reply": f"I do not see any overlapping schedule conflicts on Day {day['day_number']} ({day['date']}).",
            "action": None,
            "trip_id": trip_context["trip"]["id"],
            "conflicts": []
        }

    conflict_text = "; ".join(
        f"{_format_item(left)} overlaps with {_format_item(right)}"
        for left, right in conflicts
    )

    return {
        "reply": f"Schedule conflicts on Day {day['day_number']} ({day['date']}): {conflict_text}.",
        "action": None,
        "trip_id": trip_context["trip"]["id"],
        "conflicts": [
            {"left": left, "right": right}
            for left, right in conflicts
        ]
    }
