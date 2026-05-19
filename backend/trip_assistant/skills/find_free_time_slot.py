from fastapi import HTTPException

from trip_assistant.skills.edit_item_time import time_to_minutes


DAY_START = "08:00"
DAY_END = "21:00"


def _minutes_to_hhmm(minutes):
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def _find_day(trip_context, action):
    day_number = action.get("day_number")
    target_date = action.get("date")

    for day in trip_context["days"]:
        if day_number and day["day_number"] == day_number:
            return day
        if target_date and day["date"] == target_date:
            return day

    return None


def _duration_minutes(action):
    duration = action.get("duration_minutes") or 60

    try:
        duration = int(duration)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Duration must be a number of minutes")

    if duration <= 0:
        raise HTTPException(status_code=400, detail="Duration must be greater than zero")

    return duration


def execute_find_free_time_slot(trip_context, action):
    day = _find_day(trip_context, action)

    if not day:
        raise HTTPException(status_code=404, detail="Day not found")

    min_duration = _duration_minutes(action)
    day_start = time_to_minutes(DAY_START)
    day_end = time_to_minutes(DAY_END)

    busy_ranges = []
    for item in day["items"]:
        start = max(day_start, time_to_minutes(item["start_time"]))
        end = min(day_end, time_to_minutes(item["end_time"]))
        if start < end:
            busy_ranges.append((start, end, item))

    busy_ranges.sort(key=lambda busy: busy[0])

    free_slots = []
    cursor = day_start

    for start, end, _item in busy_ranges:
        if start > cursor and start - cursor >= min_duration:
            free_slots.append({
                "start_time": _minutes_to_hhmm(cursor),
                "end_time": _minutes_to_hhmm(start),
                "duration_minutes": start - cursor
            })
        cursor = max(cursor, end)

    if day_end > cursor and day_end - cursor >= min_duration:
        free_slots.append({
            "start_time": _minutes_to_hhmm(cursor),
            "end_time": _minutes_to_hhmm(day_end),
            "duration_minutes": day_end - cursor
        })

    if not free_slots:
        return {
            "reply": (
                f"I could not find a free slot of at least {min_duration} minutes "
                f"on Day {day['day_number']} between {DAY_START} and {DAY_END}."
            ),
            "action": None,
            "trip_id": trip_context["trip"]["id"]
        }

    slot_text = "; ".join(
        f"{slot['start_time']}-{slot['end_time']} ({slot['duration_minutes']} min)"
        for slot in free_slots
    )

    return {
        "reply": (
            f"Free slots on Day {day['day_number']} ({day['date']}) "
            f"for at least {min_duration} minutes: {slot_text}."
        ),
        "action": None,
        "trip_id": trip_context["trip"]["id"],
        "free_slots": free_slots
    }
