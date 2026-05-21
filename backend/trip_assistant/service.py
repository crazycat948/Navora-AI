import json
import os

from fastapi import HTTPException
from openai import OpenAI
from sqlalchemy import text

from database import SessionLocal
from .prompts import build_trip_action_prompt, build_trip_chat_prompt
from .graphs.schedule_conflict import run_schedule_conflict_graph
from .skills.add_attraction import execute_add_attraction
from .skills.add_user_place import execute_add_user_place
from .skills.app_help import execute_app_help
from .skills.ask_weather import execute_ask_weather
from .skills.delete_items import execute_delete_items
from .skills.destination_guard import validate_destination_place
from .skills.edit_item_time import execute_edit_item_time
from .skills.explain_conflict import execute_explain_conflict
from .skills.find_free_time_slot import execute_find_free_time_slot
from .skills.insert_attraction_available_slot import prepare_insert_attraction_available_slot
from .skills.lock_item import execute_lock_item
from .skills.move_item_to_day import execute_move_item_to_day, prepare_move_item_to_day
from .skills.replace_item import execute_replace_item
from .skills.resolve_schedule_conflict import execute_resolve_schedule_conflict

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def load_trip_context(db, trip_id: int, user_id: int):
    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id
          AND user_id = :user_id;
    """), {
        "trip_id": trip_id,
        "user_id": user_id
    }).mappings().fetchone()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    days = db.execute(text("""
        SELECT *
        FROM itinerary_days
        WHERE trip_id = :trip_id
        ORDER BY day_number;
    """), {"trip_id": trip_id}).mappings().fetchall()

    result_days = []

    for day in days:
        items = db.execute(text("""
            SELECT id, item_type, start_time, end_time, name, address, notes, locked, order_index
            FROM itinerary_items
            WHERE day_id = :day_id
            ORDER BY start_time, end_time;
        """), {"day_id": day["id"]}).mappings().fetchall()

        result_days.append({
            "id": day["id"],
            "date": str(day["date"]),
            "day_number": day["day_number"],
            "theme": day["theme"],
            "notes": day["notes"],
            "items": [dict(item) for item in items]
        })

    return {
        "trip": dict(trip),
        "days": result_days
    }


def parse_chat_response(raw_text):
    raw_text = raw_text.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        parsed = json.loads(raw_text)
        if not isinstance(parsed, dict):
            return {
                "reply": raw_text,
                "action": None
            }
        parsed.setdefault("reply", "")
        parsed.setdefault("action", None)
        return parsed
    except json.JSONDecodeError:
        return {
            "reply": raw_text,
            "action": None
        }


def generate_trip_chat_reply(trip_context, message, history=None):
    prompt = build_trip_chat_prompt(
        trip_context=trip_context,
        message=message,
        history=history
    )

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    return parse_chat_response(response.output_text)


def looks_like_action_request(message):
    message_lower = message.lower()
    action_words = [
        "replace", "swap", "change", "remove", "delete", "move",
        "reschedule", "set", "start", "end", "add", "append", "insert",
        "visit", "go to", "include", "weather", "rain", "sunny", "cloudy",
        "temperature", "forecast", "lock", "unlock", "free", "available",
        "availability", "open slot", "free slot", "time slot", "conflict",
        "overlap", "why can't", "why cant", "help", "how to", "how do i",
        "how can i", "what can you do", "use this", "use navora", "website"
    ]
    return any(word in message_lower for word in action_words)


def extract_trip_action(trip_context, message):
    prompt = build_trip_action_prompt(
        trip_context=trip_context,
        message=message
    )

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt
    )

    return parse_chat_response(response.output_text).get("action")


def build_confirmation_reply(action):
    action_type = action.get("type")

    if action_type == "replace_item":
        preference = action.get("preference") or "a new alternative"
        return f"I can replace item #{action.get('item_id')} with {preference}. Please confirm before I make the change."

    if action_type == "add_attraction":
        preference = action.get("preference") or "a new attraction"
        time_text = ""
        if action.get("start_time") and action.get("end_time"):
            time_text = f" at {action.get('start_time')}-{action.get('end_time')}"
        return f"I can add {preference} to Day {action.get('day_number')}{time_text}. Please confirm before I make the change."

    if action_type == "add_user_place":
        return (
            f"I can add {action.get('place_name')} to Day {action.get('day_number')}. "
            "Please confirm before I make the change."
        )

    if action_type == "delete_items":
        item_ids = ", ".join(f"#{item_id}" for item_id in action.get("item_ids", []))
        return f"I can delete item(s) {item_ids}. Please confirm before I make the change."

    if action_type == "lock_item":
        return f"I can lock item #{action.get('item_id')}. Please confirm before I make the change."

    if action_type == "unlock_item":
        return f"I can unlock item #{action.get('item_id')}. Please confirm before I make the change."

    if action_type == "move_item_to_day":
        return (
            f"I can move item #{action.get('item_id')} to Day {action.get('day_number')}. "
            "Please confirm before I make the change."
        )

    if action_type == "edit_item_time":
        return (
            f"I can change item #{action.get('item_id')} to "
            f"{action.get('start_time')}-{action.get('end_time')}. "
            "Please confirm before I make the change."
        )

    return "Please confirm before I make the change."


def ensure_action_for_action_request(trip_context, message, chat_result):
    if chat_result.get("action") or not looks_like_action_request(message):
        return chat_result

    action = extract_trip_action(trip_context, message)

    if not action:
        reply = chat_result.get("reply") or "I need a little more detail before I can make that change."
        reply = reply.replace("Please confirm", "Please specify the exact item")
        reply = reply.replace("please confirm", "please specify the exact item")
        return {
            "reply": reply,
            "action": None
        }

    return {
        "reply": build_confirmation_reply(action),
        "action": action
    }


def time_to_minutes(value):
    time_text = str(value)[:5]
    hours, minutes = time_text.split(":")
    return int(hours) * 60 + int(minutes)


def validate_edit_item_time_action(trip_context, chat_result):
    action = chat_result.get("action")

    if not action or action.get("type") != "edit_item_time":
        return chat_result

    item_id = action.get("item_id")
    start_time = action.get("start_time")
    end_time = action.get("end_time")

    target_day = None
    target_item = None

    for day in trip_context["days"]:
        for item in day["items"]:
            if item["id"] == item_id:
                target_day = day
                target_item = item
                break
        if target_item:
            break

    if not target_item:
        return {
            "reply": "I could not find that item in this trip. Please reference a visible item name or ID.",
            "action": None
        }

    try:
        start_minutes = time_to_minutes(start_time)
        end_minutes = time_to_minutes(end_time)
    except (TypeError, ValueError):
        return {
            "reply": "I need the new time in HH:MM format before I can propose that change.",
            "action": None
        }

    if start_minutes >= end_minutes:
        return {
            "reply": "That time range is invalid because the start time must be before the end time.",
            "action": None
        }

    conflicts = []
    for item in target_day["items"]:
        if item["id"] == item_id:
            continue

        existing_start = time_to_minutes(item["start_time"])
        existing_end = time_to_minutes(item["end_time"])

        if start_minutes < existing_end and end_minutes > existing_start:
            conflicts.append(item)

    if conflicts:
        conflict_text = ", ".join(
            f"#{item['id']} {item['name']} ({str(item['start_time'])[:5]}-{str(item['end_time'])[:5]})"
            for item in conflicts
        )
        return {
            "reply": (
                f"That change would conflict on Day {target_day['day_number']} "
                f"({target_day['date']}) with {conflict_text}. "
                "Please choose a different time or ask me to move the conflicting item."
            ),
            "action": None
        }

    return chat_result


def validate_action_targets(trip_context, chat_result):
    action = chat_result.get("action")

    if not action or action.get("type") not in [
        "replace_item",
        "move_item_to_day",
        "lock_item",
        "unlock_item",
        "app_help",
        "add_attraction",
        "insert_attraction_available_slot",
        "add_user_place",
        "ask_weather",
        "find_free_time_slot",
        "explain_conflict"
    ]:
        return chat_result

    if action.get("type") in [
        "app_help",
        "add_attraction",
        "insert_attraction_available_slot",
        "add_user_place",
        "ask_weather",
        "find_free_time_slot",
        "explain_conflict"
    ]:
        day_number = action.get("day_number")
        target_date = action.get("date")
        if action.get("type") == "app_help":
            return chat_result
        if action.get("type") == "explain_conflict" and action.get("item_id"):
            if day_number or target_date:
                target_day_exists = any(
                    (day_number and day["day_number"] == day_number) or
                    (target_date and day["date"] == target_date)
                    for day in trip_context["days"]
                )
                if not target_day_exists:
                    return {
                        "reply": "I could not find that day in this trip. Please choose a visible day number.",
                        "action": None
                    }

            for day in trip_context["days"]:
                for item in day["items"]:
                    if item["id"] == action.get("item_id"):
                        return chat_result
            return {
                "reply": "I could not find that item in this trip. Please reference a visible item name or ID.",
                "action": None
            }
        for day in trip_context["days"]:
            if day_number and day["day_number"] == day_number:
                return chat_result
            if target_date and day["date"] == target_date:
                return chat_result

        return {
            "reply": "I could not find that day in this trip. Please choose a visible day number.",
            "action": None
        }

    item_id = action.get("item_id")
    for day in trip_context["days"]:
        for item in day["items"]:
            if item["id"] == item_id:
                return chat_result

    return {
        "reply": "I could not find that item in this trip. Please reference a visible item name or ID.",
        "action": None
    }


def validate_user_place_destination(trip_context, chat_result):
    action = chat_result.get("action")

    if not action or action.get("type") != "add_user_place":
        return chat_result

    place_name = (action.get("place_name") or "").strip()

    destination_city = trip_context["trip"]["destination_city"]
    guard_result = validate_destination_place(
        place_name=place_name,
        destination_city=destination_city,
        has_car=trip_context["trip"].get("has_car", False)
    )

    if guard_result["status"] == "blocked":
        return {
            "reply": guard_result["message"],
            "action": None
        }

    action["validated_place"] = guard_result["place"]

    return chat_result


def run_trip_chat(trip_id: int, user_id: int, message: str, history=None):
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    db = SessionLocal()
    try:
        trip_context = load_trip_context(db, trip_id, user_id)

        chat_result = generate_trip_chat_reply(
            trip_context=trip_context,
            message=message.strip(),
            history=history or []
        )
        chat_result = ensure_action_for_action_request(trip_context, message.strip(), chat_result)
        chat_result = validate_action_targets(trip_context, chat_result)
        chat_result = validate_user_place_destination(trip_context, chat_result)
        chat_result = prepare_move_item_to_day(trip_context, chat_result)
        chat_result = prepare_insert_attraction_available_slot(trip_context, chat_result)

        action = chat_result.get("action") or {}
        if action.get("type") == "edit_item_time":
            graph_result = run_schedule_conflict_graph(db, trip_id, action)
            return {
                "reply": graph_result.get("reply", ""),
                "action": graph_result.get("output_action"),
                "trip_id": trip_id
            }
        if action.get("type") == "add_user_place" and action.get("start_time") and action.get("end_time"):
            graph_result = run_schedule_conflict_graph(db, trip_id, action)
            return {
                "reply": graph_result.get("reply", ""),
                "action": graph_result.get("output_action"),
                "trip_id": trip_id
            }

        action = chat_result.get("action") or {}
        if action.get("type") == "app_help":
            return execute_app_help(trip_context, action)
        if action.get("type") == "ask_weather":
            return execute_ask_weather(trip_context, action)
        if action.get("type") == "find_free_time_slot":
            return execute_find_free_time_slot(trip_context, action)
        if action.get("type") == "explain_conflict":
            return execute_explain_conflict(trip_context, action)

        return {
            "reply": chat_result.get("reply", ""),
            "action": chat_result.get("action"),
            "trip_id": trip_id
        }
    finally:
        db.close()


def execute_chat_action(trip_id: int, user_id: int, action: dict):
    action = action or {}
    action_type = action.get("type")

    if action_type not in [
        "edit_item_time",
        "delete_items",
        "lock_item",
        "unlock_item",
        "move_item_to_day",
        "replace_item",
        "add_attraction",
        "add_user_place",
        "resolve_schedule_conflict"
    ]:
        raise HTTPException(status_code=400, detail="Unsupported chat action")

    db = SessionLocal()
    try:
        trip = db.execute(text("""
            SELECT id
            FROM trips
            WHERE id = :trip_id
              AND user_id = :user_id;
        """), {
            "trip_id": trip_id,
            "user_id": user_id
        }).mappings().fetchone()

        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")

        if action_type == "edit_item_time":
            result = execute_edit_item_time(db, trip_id, action)
        elif action_type == "delete_items":
            result = execute_delete_items(db, trip_id, action)
        elif action_type == "lock_item":
            result = execute_lock_item(db, trip_id, action, locked=True)
        elif action_type == "unlock_item":
            result = execute_lock_item(db, trip_id, action, locked=False)
        elif action_type == "move_item_to_day":
            result = execute_move_item_to_day(db, trip_id, action)
        elif action_type == "replace_item":
            result = execute_replace_item(db, trip_id, action)
        elif action_type == "add_attraction":
            result = execute_add_attraction(db, trip_id, action)
        elif action_type == "resolve_schedule_conflict":
            result = execute_resolve_schedule_conflict(db, trip_id, action)
        else:
            result = execute_add_user_place(db, trip_id, action)

        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
