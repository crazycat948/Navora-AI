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
    duration = action.get("duration_minutes") or 120

    try:
        duration = int(duration)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Duration must be a number of minutes")

    if duration <= 0:
        raise HTTPException(status_code=400, detail="Duration must be greater than zero")

    return duration


def _first_open_slot(items, duration_minutes):
    day_start = time_to_minutes(DAY_START)
    day_end = time_to_minutes(DAY_END)
    busy_ranges = []

    for item in items:
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


def prepare_insert_attraction_available_slot(trip_context, chat_result):
    action = chat_result.get("action")

    if not action or action.get("type") != "insert_attraction_available_slot":
        return chat_result

    day = _find_day(trip_context, action)
    if not day:
        return {
            "reply": "I could not find that day in this trip. Please choose a visible day number.",
            "action": None
        }

    duration = _duration_minutes(action)
    start_time, end_time = _first_open_slot(day["items"], duration)

    if not start_time or not end_time:
        return {
            "reply": (
                f"I could not find an open {duration}-minute slot on Day "
                f"{day['day_number']} between {DAY_START} and {DAY_END}."
            ),
            "action": None
        }

    preference = action.get("preference") or "a new attraction"
    prepared_action = {
        "type": "add_attraction",
        "day_number": day["day_number"],
        "preference": action.get("preference") or "",
        "start_time": start_time,
        "end_time": end_time
    }

    return {
        "reply": (
            f"I found an open slot on Day {day['day_number']} from {start_time} to {end_time}. "
            f"I can add {preference} there. Please confirm before I make the change."
        ),
        "action": prepared_action
    }
