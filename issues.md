- Register page lacks email format validation — any string is accepted as a valid username （solved）
- Card edit inputs for start/end time have no format constraint — any number can be entered, invalid times are not rejected (solved)
- Card lock is incomplete: locked items can still be deleted, and there is no way to unlock a card once locked
- Date inputs have no minimum date constraint — users can select past dates, resulting in itineraries being generated for trips that have already occurred (solved)
- Attraction search radius is too narrow — currently limited to the city center only; should expand to the metro region when the user has a car (e.g. a Dallas trip should include Fort Worth attractions), and stay city-only when the user does not have a car
- Departure city and destination city are not validated to be different — a user can plan a trip from and to the same city (solved)
- Traveler type (Speedrunning / Normal / Chill) has no enforced scheduling definition — should map to explicit daily item counts: Speedrunning = 4 items/day (2 morning + 2 afternoon), Normal = 2 items/day (1 morning + 1 afternoon), Chill = 1 item/day (solved)

[FEATURE] - Add a fixed "Add Attraction" button on each day that lets the user AI-generate and append additional attraction cards freely — can be clicked multiple times, giving users full flexibility to build up or extend their itinerary beyond the initial AI-generated plan
[FEATURE] - Itinerary cards within each day should be sorted by end time; overlapping time slots (where two items share the same time range) should be blocked — if the user manually edits a card's time to conflict with another, they should be warned and prevented from saving
[FEATURE] - Allow users to add a known place they already want to visit by providing the place name/details directly; the app should help validate the place, find or suggest a time slot, and add it into the current plan

---

[PROPOSAL] AI Chatbox with Trip Editing Skills

A persistent chat interface embedded in the trip detail view that allows users to interact with their itinerary conversationally. The assistant can answer questions, suggest changes, and execute edits — but always confirms with the user before making any modifications.

Core behavior:
- User sends a message describing what they want ("move lunch to 1pm", "what's the weather like on day 3", "replace the museum with something outdoors")
- AI interprets the intent and responds with a clarifying confirmation ("Got it — you want to move lunch from 12:00 to 13:00 on Day 2. Should I go ahead?")
- User confirms or adjusts, then the AI executes the action via the existing API endpoints

Chat modes:
- Embedded trip chat — opened from the trip detail page and automatically bound to the currently viewed trip ID and itinerary content; users can ask direct plan-specific questions without repeating the trip ID
- Standalone chat page — a separate assistant page for general travel questions and trip operations; the user must already be logged in, and must provide a trip ID before the assistant can access or edit a specific plan
- Active trip context — after a standalone chat user provides a valid trip ID, the frontend can store that trip as the active context for the current chat session so the user does not need to repeat the ID in every message
- Ownership check — for standalone plan-specific service, the backend must verify that the requested trip belongs to the authenticated user before returning or editing any trip data
- No password in chat — username/password should not be collected through chat messages; authentication should rely on the existing login token/JWT

Planned skills:
- [completed] Edit item — modify the time of a specific card through chat by referencing its ID or description; AI proposes the change, user confirms, backend validates ownership/locked status/time conflicts, then updates the item
- [completed] Replace item — replace a card with a new AI-generated one based on user preference ("something more budget-friendly", "an outdoor alternative") after user confirmation
- [completed] Ask about weather — query weather for a specific trip day through chat; if hourly forecast data is available, summarize morning/midday/afternoon/evening conditions, and say when data is unavailable
- [completed] Add attraction — generate and append a new attraction card to a specific day through chat after user confirmation
- [completed] Add user-provided place — let users provide a specific place they already know they want to visit, then validate it with Google Places and insert it into the plan after confirmation
- [completed] Delete item — remove one or multiple attraction/restaurant cards through chat after user confirmation; backend validates ownership and locked status before deleting
- [pending] Detect schedule conflict — check whether a proposed time change overlaps with existing cards on the same day before saving
- [pending] Resolve schedule conflict — suggest alternative time slots or move conflicting items after user confirmation
- [pending] Reorder day itinerary — sort cards within a day by end time so the itinerary always displays in schedule order
- [pending] Optimize day schedule — reorganize a day's items based on time, trip pace, and practical spacing between activities
- [pending] Move item to another day — relocate a card to a different day while checking the target day's available time slots
- [pending] Find free time slot — identify open windows in a day where a new or moved attraction can fit
- [pending] Insert attraction into available slot — generate a new attraction and place it into a non-conflicting time window instead of blindly appending it
- [pending] Shorten or extend item duration — adjust an item's start/end time while validating that the new duration does not conflict with other cards
- [pending] Explain conflict — tell the user exactly which items overlap and why a proposed save cannot be completed
- [pending] Budget-aware replacement — replace an item with a cheaper or more premium alternative based on user preference
- [pending] Weather-aware reschedule — use weather context to suggest moving outdoor/indoor activities across days
- [pending] Location-aware route optimization — reorder or replace items to reduce unnecessary travel between attractions
- [pending] Preference-based refine — update multiple itinerary items based on broad user preferences such as "more nature", "less museums", or "family friendly"

Implementation notes:
- Upgrade LLM from gpt-4o-mini to gpt-4o for better instruction-following and natural conversation
- Display item ID on each card so users can reference specific items in chat ("can you change item #42 to start at 3pm")
- Chat history persisted per trip session (not saved to DB, lives in frontend state)
- Backend: new POST /api/trips/{trip_id}/chat endpoint — receives message + conversation history, returns AI response and optional action payload
- Backend: standalone chat endpoint should accept message + conversation history + optional active trip ID, then validate ownership before loading trip context
- Frontend: slide-in chat panel on the right side of the trip detail view
- Frontend: standalone chat page should require login and support selecting/setting an active trip ID for the current chat session
- Schedule editing must reuse the same validation rules as manual card editing: sort cards by end time and block overlapping time slots before save
- Conflict-related actions should return structured details about the conflicting item IDs, times, and suggested alternatives
