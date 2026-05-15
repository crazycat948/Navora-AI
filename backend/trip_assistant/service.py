import json
import os

from fastapi import HTTPException
from openai import OpenAI
from sqlalchemy import text

from database import SessionLocal
from .prompts import build_trip_chat_prompt
from .skills.delete_items import execute_delete_items
from .skills.edit_item_time import execute_edit_item_time

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
        return json.loads(raw_text)
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


def run_trip_chat(trip_id: int, user_id: int, message: str, history=None):
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    db = SessionLocal()
    try:
        trip_context = load_trip_context(db, trip_id, user_id)
    finally:
        db.close()

    chat_result = generate_trip_chat_reply(
        trip_context=trip_context,
        message=message.strip(),
        history=history or []
    )
    chat_result = validate_edit_item_time_action(trip_context, chat_result)

    return {
        "reply": chat_result.get("reply", ""),
        "action": chat_result.get("action"),
        "trip_id": trip_id
    }


def execute_chat_action(trip_id: int, user_id: int, action: dict):
    action = action or {}
    action_type = action.get("type")

    if action_type not in ["edit_item_time", "delete_items"]:
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
        else:
            result = execute_delete_items(db, trip_id, action)

        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
