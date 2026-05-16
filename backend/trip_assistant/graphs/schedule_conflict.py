from typing import Any, Dict, List, Optional, TypedDict

from fastapi import HTTPException
from langgraph.graph import END, StateGraph
from sqlalchemy import text

from trip_assistant.skills.edit_item_time import time_to_minutes, validate_hhmm


class ScheduleConflictState(TypedDict, total=False):
    db: Any
    trip_id: int
    action: Dict
    target_item: Optional[Dict]
    same_day_items: List[Dict]
    conflicts: List[Dict]
    resolution_plan: Optional[Dict]
    reply: str
    output_action: Optional[Dict]
    status: str


def _format_item_time(item):
    return f"{str(item['start_time'])[:5]}-{str(item['end_time'])[:5]}"


def _duration_minutes(item):
    return time_to_minutes(item["end_time"]) - time_to_minutes(item["start_time"])


def _minutes_to_hhmm(minutes):
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


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


def parse_time_edit(state: ScheduleConflictState):
    action = state["action"]
    start_time = action.get("start_time")
    end_time = action.get("end_time")

    validate_hhmm(start_time)
    validate_hhmm(end_time)

    if time_to_minutes(start_time) >= time_to_minutes(end_time):
        raise HTTPException(status_code=400, detail="Start time must be before end time")

    return {}


def load_target_context(state: ScheduleConflictState):
    db = state["db"]
    action = state["action"]
    trip_id = state["trip_id"]
    if action.get("type") == "add_user_place":
        day = db.execute(text("""
            SELECT *
            FROM itinerary_days
            WHERE trip_id = :trip_id
              AND day_number = :day_number;
        """), {
            "trip_id": trip_id,
            "day_number": action.get("day_number")
        }).mappings().fetchone()

        if not day:
            raise HTTPException(status_code=404, detail="Day not found")

        same_day_items = db.execute(text("""
            SELECT id, name, start_time, end_time, locked
            FROM itinerary_items
            WHERE day_id = :day_id
            ORDER BY start_time, end_time;
        """), {"day_id": day["id"]}).mappings().fetchall()

        return {
            "target_item": {
                "id": None,
                "name": action.get("place_name") or "new place",
                "day_id": day["id"],
                "start_time": action.get("start_time"),
                "end_time": action.get("end_time"),
                "locked": False
            },
            "same_day_items": [dict(item) for item in same_day_items]
        }

    item_id = action.get("item_id")

    target_item = db.execute(text("""
        SELECT *
        FROM itinerary_items
        WHERE id = :item_id
          AND trip_id = :trip_id;
    """), {
        "item_id": item_id,
        "trip_id": trip_id
    }).mappings().fetchone()

    if not target_item:
        raise HTTPException(status_code=404, detail="Itinerary item not found")

    if target_item["locked"]:
        raise HTTPException(status_code=400, detail="This item is locked and cannot be edited")

    same_day_items = db.execute(text("""
        SELECT id, name, start_time, end_time, locked
        FROM itinerary_items
        WHERE day_id = :day_id
          AND id != :item_id
        ORDER BY start_time, end_time;
    """), {
        "day_id": target_item["day_id"],
        "item_id": item_id
    }).mappings().fetchall()

    return {
        "target_item": dict(target_item),
        "same_day_items": [dict(item) for item in same_day_items]
    }


def validate_target_slot(state: ScheduleConflictState):
    action = state["action"]
    same_day_items = state["same_day_items"]
    start_time = action["start_time"]
    end_time = action["end_time"]

    conflicts = []
    for item in same_day_items:
        if _overlaps(start_time, end_time, [item]):
            conflicts.append(item)

    if not conflicts:
        if action.get("type") == "add_user_place":
            return {
                "status": "no_conflict",
                "output_action": action,
                "reply": (
                    f"I can add {action.get('place_name')} to Day {action.get('day_number')} "
                    f"at {start_time}-{end_time}. Please confirm before I make the change."
                )
            }

        return {
            "status": "no_conflict",
            "output_action": action,
            "reply": (
                f"I can move item #{action['item_id']} to "
                f"{start_time}-{end_time}. Please confirm before I make the change."
            )
        }

    return {
        "status": "conflict",
        "conflicts": conflicts
    }


def route_after_target_validation(state: ScheduleConflictState):
    return "end" if state["status"] == "no_conflict" else "generate_resolution_plan"


def _candidate_slots(duration):
    starts = [
        "08:00", "09:00", "10:00", "11:00",
        "14:00", "15:00", "16:00", "17:00",
        "18:00", "19:00"
    ]

    for start_time in starts:
        start_minutes = time_to_minutes(start_time)
        end_minutes = start_minutes + duration
        if end_minutes <= 21 * 60:
            yield start_time, _minutes_to_hhmm(end_minutes)


def generate_resolution_plan(state: ScheduleConflictState):
    action = state["action"]
    target_item = state["target_item"]
    same_day_items = state["same_day_items"]
    conflicts = state["conflicts"]

    proposed_moves = []
    simulated_items = []

    for item in same_day_items:
        if item["id"] not in [conflict["id"] for conflict in conflicts]:
            simulated_items.append(item)

    fixed_target = {
        "id": target_item["id"],
        "name": target_item["name"],
        "start_time": action["start_time"],
        "end_time": action["end_time"]
    }
    if fixed_target["id"] is not None:
        simulated_items.append(fixed_target)
    else:
        simulated_items.append({
            "id": -1,
            "name": fixed_target["name"],
            "start_time": fixed_target["start_time"],
            "end_time": fixed_target["end_time"]
        })

    for conflict in conflicts:
        if conflict["locked"]:
            return {
                "status": "unresolved",
                "reply": (
                    f"That time conflicts with locked item #{conflict['id']} "
                    f"{conflict['name']} ({_format_item_time(conflict)}), so I cannot move it automatically."
                ),
                "output_action": None
            }

        duration = _duration_minutes(conflict)
        chosen_slot = None

        for start_time, end_time in _candidate_slots(duration):
            if not _overlaps(start_time, end_time, simulated_items, ignore_ids={conflict["id"]}):
                chosen_slot = (start_time, end_time)
                break

        if not chosen_slot:
            return {
                "status": "unresolved",
                "reply": (
                    "I found a conflict, but I could not find a clean open slot "
                    "for the conflicting item on the same day."
                ),
                "output_action": None
            }

        move = {
            "item_id": conflict["id"],
            "name": conflict["name"],
            "old_start_time": str(conflict["start_time"])[:5],
            "old_end_time": str(conflict["end_time"])[:5],
            "start_time": chosen_slot[0],
            "end_time": chosen_slot[1],
            "reason": "Keeps the same duration while avoiding the fixed requested time."
        }
        proposed_moves.append(move)
        simulated_items.append({
            "id": conflict["id"],
            "name": conflict["name"],
            "start_time": chosen_slot[0],
            "end_time": chosen_slot[1]
        })

    return {
        "status": "resolution_generated",
        "resolution_plan": {
            "fixed_change": {
                "item_id": action.get("item_id"),
                "start_time": action["start_time"],
                "end_time": action["end_time"]
            },
            "proposed_moves": proposed_moves
        }
    }


def validate_resolution_plan(state: ScheduleConflictState):
    if state.get("status") == "unresolved":
        return {}

    action = state["action"]
    plan = state["resolution_plan"]
    fixed_change = plan["fixed_change"]
    proposed_moves = plan["proposed_moves"]
    same_day_items = state["same_day_items"]
    target_item = state["target_item"]

    simulated_items = []
    moved_ids = {move["item_id"] for move in proposed_moves}

    simulated_items.append({
        "id": target_item["id"] if target_item["id"] is not None else -1,
        "name": target_item["name"],
        "start_time": fixed_change["start_time"],
        "end_time": fixed_change["end_time"]
    })

    for item in same_day_items:
        if item["id"] not in moved_ids:
            simulated_items.append(item)

    for move in proposed_moves:
        if _overlaps(move["start_time"], move["end_time"], simulated_items):
            return {
                "status": "unresolved",
                "reply": "I generated a resolution plan, but it still has a schedule conflict.",
                "output_action": None
            }
        simulated_items.append({
            "id": move["item_id"],
            "name": move["name"],
            "start_time": move["start_time"],
            "end_time": move["end_time"]
        })

    move_text = "; ".join(
        f"move #{move['item_id']} {move['name']} from "
        f"{move['old_start_time']}-{move['old_end_time']} to {move['start_time']}-{move['end_time']}"
        for move in proposed_moves
    )

    return {
        "status": "resolution_valid",
        "reply": (
            f"That time conflicts with another item. To keep "
            f"{target_item['name']} at {fixed_change['start_time']}-{fixed_change['end_time']}, "
            f"I can {move_text}. "
            "Please confirm before I make these changes."
        ),
        "output_action": {
            "type": "resolve_schedule_conflict",
            "fixed_change": fixed_change,
            "proposed_moves": proposed_moves,
            "pending_add": action if action.get("type") == "add_user_place" else None
        }
    }


def build_schedule_conflict_graph():
    graph = StateGraph(ScheduleConflictState)

    graph.add_node("parse_time_edit", parse_time_edit)
    graph.add_node("load_target_context", load_target_context)
    graph.add_node("validate_target_slot", validate_target_slot)
    graph.add_node("generate_resolution_plan", generate_resolution_plan)
    graph.add_node("validate_resolution_plan", validate_resolution_plan)

    graph.set_entry_point("parse_time_edit")
    graph.add_edge("parse_time_edit", "load_target_context")
    graph.add_edge("load_target_context", "validate_target_slot")
    graph.add_conditional_edges(
        "validate_target_slot",
        route_after_target_validation,
        {
            "end": END,
            "generate_resolution_plan": "generate_resolution_plan"
        }
    )
    graph.add_edge("generate_resolution_plan", "validate_resolution_plan")
    graph.add_edge("validate_resolution_plan", END)

    return graph.compile()


schedule_conflict_graph = build_schedule_conflict_graph()


def run_schedule_conflict_graph(db, trip_id: int, action: dict):
    return schedule_conflict_graph.invoke({
        "db": db,
        "trip_id": trip_id,
        "action": action,
        "conflicts": [],
        "resolution_attempts": [],
        "current_resolution_plan": None,
        "awaiting_confirmation": False,
        "confirmed": False
    })
