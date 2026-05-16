# LangGraph Infrastructure

This document is the central place for all planned LangGraph architecture in Navora AI.

Any future assistant workflow that uses LangGraph should be documented here instead of creating a separate standalone architecture file.

## Documentation Rule

- Keep shared LangGraph conventions in the top-level infrastructure sections.
- Add each LangGraph-powered skill as its own section in this file.
- Each skill section should explain its goal, state shape, workflow graph, node responsibilities, confirmation behavior, and execution safety rules.
- If a skill becomes large, it can link to implementation files, but the architecture summary should still live here.

---

# Skill: Schedule Conflict Resolution

This section describes the planned LangGraph workflow for the schedule-conflict skill in the Navora AI trip assistant.

## Goal

When a user asks to change an itinerary item's time, the assistant should:

- Treat the user's requested time as the fixed target time.
- Check whether the requested time conflicts with other items on the same day.
- If there is no conflict, ask for confirmation and apply the edit.
- If there is a conflict, explain the conflict and ask whether the user wants the assistant to resolve it.
- If the user agrees, generate alternative moves for the conflicting item(s).
- Validate every generated plan deterministically before asking the user to confirm.
- Apply changes only after user confirmation.

## Key Principle

The user's requested time is a hard constraint.

Example:

```txt
Move Griffith Observatory to 10:00-12:00.
```

The assistant should keep Griffith Observatory at `10:00-12:00` and try to move the conflicting item(s), rather than changing the user's requested target time.

## State Shape

```json
{
  "trip_id": 123,
  "user_id": 7,
  "message": "Move Griffith Observatory to 10am",
  "target_change": {
    "item_id": 12,
    "day_id": 3,
    "start_time": "10:00",
    "end_time": "12:00"
  },
  "conflicts": [
    {
      "item_id": 15,
      "name": "Griffith Park",
      "start_time": "09:00",
      "end_time": "11:00"
    }
  ],
  "resolution_attempts": [],
  "current_resolution_plan": null,
  "awaiting_confirmation": false,
  "confirmed": false,
  "final_reply": null
}
```

## Workflow

```txt
parse_time_edit
  ↓
validate_target_slot
  ↓ no conflict
confirm_direct_edit
  ↓ user confirms
execute_direct_edit
  ↓
end

validate_target_slot
  ↓ conflict
explain_conflict
  ↓
ask_resolution_permission
  ↓ user agrees
generate_resolution_plan
  ↓
validate_resolution_plan
  ↓ valid
confirm_resolution
  ↓ user confirms
execute_batch_update
  ↓
end

validate_resolution_plan
  ↓ invalid
generate_alternative_plan

confirm_resolution
  ↓ user rejects but wants another option
generate_alternative_plan

confirm_resolution
  ↓ user cancels
end_without_changes
```

## Node Responsibilities

### `parse_time_edit`

Extracts the user's requested edit.

Output:

```json
{
  "item_id": 12,
  "start_time": "10:00",
  "end_time": "12:00"
}
```

If the item or time is unclear, the graph should stop and ask a clarification question.

### `validate_target_slot`

Deterministically checks whether the target item can move to the requested time.

Validation rules:

- Item belongs to the current trip.
- Item is not locked.
- Time format is valid.
- `start_time < end_time`.
- Conflict checks only compare against items on the same `day_id`.

If there is no conflict, continue to direct confirmation.

If there is a conflict, store the conflicting items in state.

### `confirm_direct_edit`

Asks the user to confirm the simple edit.

Example:

```txt
I can move Griffith Observatory to 10:00-12:00. Confirm?
```

### `execute_direct_edit`

Applies the target item update to the database.

This node should reuse the same backend validation as `validate_target_slot` before writing.

### `explain_conflict`

Explains the conflict clearly.

Example:

```txt
That time conflicts with Griffith Park, which is scheduled from 09:00-11:00 on Day 2.
```

### `ask_resolution_permission`

Asks whether the user wants the assistant to resolve the conflict by moving other item(s).

Example:

```txt
Do you want me to keep Griffith Observatory at 10:00-12:00 and try moving Griffith Park instead?
```

If the user says no, end without changes.

### `generate_resolution_plan`

Generates a plan while keeping the user's requested time fixed.

Example output:

```json
{
  "fixed_change": {
    "item_id": 12,
    "start_time": "10:00",
    "end_time": "12:00"
  },
  "proposed_moves": [
    {
      "item_id": 15,
      "start_time": "14:00",
      "end_time": "16:00",
      "reason": "Keeps the same duration and avoids lunch."
    }
  ]
}
```

### `validate_resolution_plan`

Deterministically validates the generated plan.

Checks:

- The fixed target change is preserved.
- Moved items are not locked.
- All proposed times are valid.
- No moved item conflicts with other items on the same day.
- No moved item conflicts with another moved item.
- The plan does not move items to another day unless the user explicitly allowed cross-day moves.

If invalid, route to `generate_alternative_plan`.

### `generate_alternative_plan`

Generates another plan using the previous failed/rejected plans as negative examples.

The graph should cap attempts, for example:

```txt
max_resolution_attempts = 3
```

If no valid plan can be found, end with a clear message.

### `confirm_resolution`

Shows the full plan to the user before writing.

Example:

```txt
To keep Griffith Observatory at 10:00-12:00, I need to move Griffith Park from 09:00-11:00 to 14:00-16:00. Confirm?
```

User options:

- Confirm: execute the batch update.
- Reject and ask for another option: generate alternative plan.
- Cancel: end without changes.

### `execute_batch_update`

Applies the fixed change and all approved moves in one transaction.

This should be atomic:

- If any update fails validation, roll back the full batch.
- Return updated items to the frontend so cards can refresh immediately.

## Why LangGraph

This skill needs LangGraph because it is no longer a simple single-action tool call.

It requires:

- Multi-step state.
- Human confirmation.
- Branching based on conflict/no-conflict.
- Repeated plan generation attempts.
- Deterministic validation between LLM steps.
- Safe transactional execution.

This is the point where the assistant starts behaving like a workflow engine rather than a simple CRUD chatbot.
