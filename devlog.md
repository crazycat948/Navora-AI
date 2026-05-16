# 5/2/2026 

- Started development of a new project: **AI Travel Planner**
- Defined project scope and core idea (multi-agent travel planning system)
- Designed questionnaire structure for user input
- Planned system architecture (Orchestrator + 5 specialized agents)
- Defined data flow and agent responsibilities
- Selected technology stack (FastAPI, React, PostgreSQL, OpenAI API, LangGraph)
- Designed database schema for user accounts, trips, and modular itinerary structure
- Defined API endpoints for itinerary generation and editing
- Designed UI/UX concept with modular itinerary cards
- Completed full project proposal documentation


# 5/3/2026

successfully connected front and back 
also back and DB


# 5/4/2026

Heavy backend development day. Built out the full core feature set of the itinerary system.

**Backend — API Endpoints**
- `POST /api/trips/create` — creates a trip record in the database with all user inputs (destination, dates, budget, traveler type, car/hotel/flight flags)
- `POST /api/trips/{trip_id}/generate-itinerary` — mock itinerary generator (hardcoded LA items) used for early DB structure testing
- `POST /api/trips/{trip_id}/generate-ai-itinerary` — real AI-powered itinerary generation via OpenAI; clears existing itinerary before regenerating to prevent duplicates
- `GET /api/trips/{trip_id}` — fetches full trip detail including all days and itinerary items, nested and ordered
- `GET /api/trips` — returns full trip history ordered by creation time
- `GET /api/trips/{trip_id}/ai-preview` — returns raw AI-generated JSON without saving to DB (used for debugging)
- `PATCH /api/itinerary-items/{id}` — partial update on any itinerary item (time, name, address, notes, locked status)
- `POST /api/itinerary-items/{id}/replace` — replaces a single item with a new AI-generated one; passes existing items on the same day to the prompt to avoid duplicate recommendations
- `DELETE /api/itinerary-items/{id}` — deletes a single itinerary item from the database

**Backend — Other**
- Added CORS middleware to allow frontend to communicate with backend during local development
- Connected OpenAI API via `ai_service.py`; built `generate_itinerary_json()` to produce structured day-by-day itinerary JSON and `replace_itinerary_item_json()` to generate a single replacement item
- Prompt engineering: enforced JSON-only output, passed existing same-day items to prevent duplicates on replace
- Added loading state endpoint `/openai-test` for verifying API key connection

**Database**
- Tables in active use: `trips`, `itinerary_days`, `itinerary_items`
- Each itinerary item is stored as an independent record to support modular editing (replace, lock, delete per card)
- `itinerary_days` and `itinerary_items` are cleared before regeneration to keep data clean

**Frontend (Test UI)**
- Built a minimal HTML/JS test frontend (`index.html` + `script.js`) connected directly to the backend
- Supports: create trip, generate AI itinerary, view trip detail, view history
- Each itinerary item renders as a card with inline Update / Replace / Lock / Delete buttons
- Replace and Update use `updateSingleCard()` for instant in-place card refresh without reloading the full itinerary
- Added loading indicator that shows status messages during async API calls (generating, replacing, updating, deleting)

**Next Steps**
- Begin development of the multi-agent architecture (Orchestrator, Attraction Agent, Food Agent, Weather Agent, Travel Logistics Agent)
- Integrate external APIs (Google Places, Yelp, AccuWeather, Amadeus) to replace mock/AI-only data with real-world verified results
- Replace the test frontend with the full React UI (already scaffolded)


# 5/5/2026

Agent development day. Integrated real external APIs and built out three specialized agents.

**API Strategy Change**
- Original plan called for Google Places, Yelp Fusion, and AccuWeather as separate APIs
- After exploring the Google Places API (New), decided to consolidate: Google Places New covers attractions, restaurants, ratings, addresses, and place IDs comprehensively enough to replace Yelp entirely
- Similarly, replaced AccuWeather with the Open-Meteo weather API (free, no key required, returns hourly forecasts by coordinates)
- Final external API stack: **Google Places API (New)** + **Open-Meteo** — simpler, cheaper, and sufficient for all data needs

**Attraction Agent (`attraction_agent.py`)**
- Takes trip data (destination city, traveler type, budget) as input
- Calls `places_service.py` which hits the Google Places New Text Search API (`POST https://places.googleapis.com/v1/places:searchText`)
- Queries for top tourist attractions in the destination city, returns up to 5 results
- Each result includes: `place_id`, `name`, `formatted_address`, `rating`
- Output is passed directly into the itinerary generation prompt so the AI uses real verified place data instead of hallucinated names
- Test endpoint: `GET /api/trips/{trip_id}/attractions`

**Food Agent (`food_agent.py`)**
- Same architecture as Attraction Agent but queries for restaurants
- Calls Google Places New with a restaurant-focused query (e.g. "best restaurants in {city}")
- Returns up to 5 real restaurant results with place IDs and addresses
- Output fed into the itinerary prompt alongside attraction data
- Test endpoint: `GET /api/trips/{trip_id}/foods`

**Weather Agent (`weather_agent.py`)**
- Takes trip destination coordinates and date range as input
- Calls `weather_service.py` which hits Open-Meteo (`https://api.open-meteo.com/v1/forecast`)
- Returns day-by-day weather summary: temperature range, precipitation probability, condition label (Sunny / Cloudy / Rainy)
- Output passed into the itinerary prompt so the AI can adjust activity scheduling based on weather (e.g. indoor venues on rainy days, outdoor attractions on sunny days)
- Test endpoint: `GET /api/trips/{trip_id}/weather`, `/weather-test`

**Prompt Engineering Updates (`ai_service.py`)**
- `generate_itinerary_json()` now accepts `attraction_data`, `food_data`, and `weather_data` as optional parameters
- All three agent outputs are injected into the prompt before generation
- Added strict rules to the prompt: AI must ONLY use places from agent recommendations, must include valid `external_place_id` for every item, and must never invent attraction or restaurant names
- `external_place_id` field added to the itinerary item JSON schema and to the database insert

**Database**
- Added `external_place_id TEXT` column to `itinerary_items` table via `ALTER TABLE`
- This allows each item to be traced back to its Google Places source for future use (photos, reviews, maps links)

**Next Steps**
- Build the Orchestrator Agent to coordinate all specialized agents and manage the full generation pipeline
- Begin full React frontend development (the test HTML UI has served its purpose)


# 5/6/2026

Orchestrator Agent completed. Backend is now feature-complete. Transitioning to frontend development.

**Orchestrator Agent (`orchestrator_agent.py`)**
- Built the central coordinator that manages the full multi-agent pipeline
- On each call, the Orchestrator runs all three specialized agents in sequence: Attraction Agent → Food Agent → Weather Agent
- Collects and packages all three outputs into a unified `agent_outputs` dict (`attractions`, `foods`, `weather`)
- Returns both `agent_outputs` and a `summary` so the caller has full visibility into what each agent produced
- This design keeps `generate_ai_itinerary()` clean: it delegates all data-gathering to the Orchestrator and only handles DB persistence itself
- `main.py` updated to import and call `run_orchestrator()` instead of calling the three agents individually
- Added `GET /api/trips/{trip_id}/orchestrator-test` endpoint — returns the raw Orchestrator output (all three agent outputs) without generating or saving an itinerary, useful for verifying agent data before committing a full generation

**Prompt Engineering Upgrade (`ai_service.py`)**
- Rewrote the `generate_itinerary_json()` system prompt with stricter, more explicit planning constraints
- Reframed the agent identity: now explicitly "the Itinerary Planner Agent" rather than a generic AI travel planner
- Added hard prohibition on vague filler activities (e.g. "Explore the beach", "Walk around downtown", "Shopping time") — every item must come from agent data
- Enforced daily item count: 2–4 items per day to prevent over-scheduling
- Added mealtime anchors: lunch 12:00–14:00, dinner 17:30–20:00
- Added explicit fallback rule: if agent data runs out, generate fewer items rather than inventing new places
- `source_api` field constrained to `"Google Places"` or `"Google Places + OpenAI"` to match actual agent outputs

**Backend Status**
- All core API endpoints are implemented and tested
- Multi-agent pipeline (Orchestrator + Attraction + Food + Weather) is fully wired up
- AI itinerary generation uses real Google Places data and Open-Meteo weather with strict prompt guardrails
- Backend is considered feature-complete for the current scope

**Next Steps**
- Begin full React frontend development
- Build the trip creation form, itinerary view, and per-card editing UI
- Connect frontend to all existing backend API endpoints


# 5/7/2026

Frontend development day. Gave the test UI a proper look and feel.

**UI Redesign**
- Restructured `index.html` with semantic layout: fixed navbar, 360px left sidebar for the form, and a scrollable right content panel
- Pulled in Inter font via Google Fonts; built a full design system in `style.css` (color palette, button variants, form inputs, card styles)
- Left panel: trip creation form with labeled inputs, date pickers, checkboxes, and action buttons
- Right panel: day-by-day itinerary with styled cards per item; attraction cards use a blue badge, restaurant cards use an orange badge
- Raw API output collapsed into a `<details>` block at the bottom so it's accessible but not in the way

**Itinerary Cards**
- Refactored `renderTripDetail` and `updateSingleCard` to share a single `cardHTML()` helper
- Each card shows type badge, name, time range, address, notes, and inline edit inputs
- Locked items get a gold border and 🔒 badge

**Weather Emoji on Cards**
- `getTripDetail()` now parallel-fetches `/weather` alongside the trip data
- Builds a `weatherMap` keyed by date; each day header and card gets the matching emoji (☀️ / 🌧️ / ⛅)

**Loading Animation**
- Added a 5-ball bouncing loader that appears in the content area when AI generation starts
- Two stacked CSS animations per ball: `ball-bounce` (0.6s, physical ease curve) and `ball-color` (2.4s, `steps(4)`) — color snaps to a new value on each bounce, cycling through red-orange, deep blue, yellow-orange, and green
- Hint text below the balls with animated ellipsis (0 → 6 dots, 400ms per dot, then resets)

**Minor Improvements**
- Traveler Type changed from a free-text input to a `<select>` with three options: 🌴 Chill, 🙂 Normal, ⚡ Speedrunning

**Auth System**
- Built `auth_service.py` using `passlib` + `bcrypt` for password hashing and `python-jose` for JWT (HS256, 7-day expiry, secret key from `.env`)
- Added `POST /api/auth/register` and `POST /api/auth/login` endpoints to `main.py`
- `get_current_user_id()` helper decodes Bearer token and raises 401 on invalid/missing auth
- `POST /api/trips/create` and `GET /api/trips` are now auth-protected — trips are scoped to the logged-in user
- Added `DELETE /api/trips/{trip_id}` endpoint with ownership check; explicitly deletes `itinerary_items` and `itinerary_days` before deleting the trip (safe even though CASCADE is already in place)

**Auth Frontend**
- Created `auth.js` with `loginUser()`, `registerUser()`, `logoutUser()`, and `requireLogin()` — token stored in `localStorage`
- Built `login.html` and `register.html` with the same Inter font, deep-blue navbar, and centered card design as the main app
- `index.html` now calls `requireLogin()` on load and shows a Logout button in the navbar

**Trip History & Detail Pages**
- Created `history.html` + `history.js`: fetches the current user's trips (auth-gated), renders them as a hoverable card grid, each card links to `trip-detail.html` via `localStorage`
- Created `trip-detail.html`: reads `selectedTripId` from `localStorage`, shows bounce loader while fetching, then renders the full itinerary using the existing `renderTripDetail()` from `script.js`
- Added `deleteTrip()` to `history.js` with a confirm dialog; Delete button on each history card uses `event.stopPropagation()` to avoid triggering the card's click-to-navigate

**UX Flow Fix**
- Removed the manual Trip ID input and Generate AI Itinerary button from `index.html`
- `createTrip()` now auto-chains into itinerary generation immediately after the trip is created — one click does everything
- Trip ID is written to a hidden field internally; users never see or interact with it, preventing ID-guessing attacks on other users' trips

**City Autocomplete & Input Validation**
- Created `city_service.py` — calls Google Places Text Search with `includedType: "locality"` to restrict results to real cities only, returns up to 5 matches with name and full formatted address
- Added `GET /api/cities/search?q=` endpoint (no auth required); returns empty list for queries shorter than 2 characters
- Created `autocomplete.js` — `setupCityAutocomplete()` dynamically injects an absolutely-positioned dropdown into each city input's parent; debounces requests by 300ms, closes on blur (150ms delay to allow click to register) and on Escape
- Dropdown displays full address for disambiguation but writes only the city name into the input on selection
- Applied to both Departure City and Destination City fields in `index.html`
- Added `.city-dropdown` and `.city-dropdown-item` styles to `style.css`, consistent with the existing design system


# 5/8/2026

Hotel and flight recommendation module shipped. Backend feature-complete.

**Hotel & Flight Recommendations**
- Last planned module from the original project scope — now live
- Originally planned to integrate Amadeus API for real flight/hotel data, but since this is not a core feature of the product, decided to use the OpenAI API instead for recommendation generation
- Built `travel_recommendation_service.py`: calls OpenAI with trip context (destination, dates, budget, traveler type) and returns structured hotel and flight suggestions
- Added `POST /api/trips/{trip_id}/travel-recommendations` endpoint — triggered automatically after AI itinerary generation if `need_hotel` or `need_flight` is checked
- Results stored in `hotel_recommendations` and `flight_recommendations` tables; returned as part of the `GET /api/trips/{trip_id}` response

**Frontend**
- `createTrip()` now auto-calls the travel recommendations endpoint after itinerary generation when applicable
- `renderTripDetail()` updated to render hotel and flight cards at the bottom of the itinerary using `.rec-section`, `.rec-card` component classes
- Added corresponding CSS classes to `style.css` — consistent with the existing card design system

**Project Status**
- All originally scoped modules are now implemented
- Remaining work: UI/UX polish and final detail pass before demo


# 5/15/2026

Planning another major feature for the project today. The next development focus is an AI chatbox embedded in the trip detail view, with trip-editing skills that can understand user requests, confirm changes, and execute itinerary updates through the existing API.

**Planned Feature**
- Add a persistent conversational assistant for editing and refining trips
- Support skills such as editing, replacing, adding, deleting, rescheduling, and optimizing itinerary items
- Make the assistant schedule-aware so it can detect overlapping time slots, explain conflicts, find free windows, and prevent invalid saves
- Keep user confirmation required before any modification is applied

**Reference**
- Full proposal and skill list are documented in `issues.md`

**Embedded Trip Chatbox MVP**
- Added a fixed robot emoji button on trip detail pages as the entry point for the assistant
- Built a fixed-position chat panel with local message rendering, input handling, Enter-to-send, loading state, and assistant replies
- Connected the chatbox to a new authenticated backend chat endpoint: `POST /api/trips/{trip_id}/chat`
- Chat context is automatically bound to the currently viewed trip ID, and the backend verifies that the trip belongs to the logged-in user before loading itinerary data
- The assistant can now read the current trip, days, and itinerary items and answer plan-specific questions

**Trip Editing Skills**
- Implemented the first executable chat skill: edit item time
- The assistant proposes a time change, the frontend shows Confirm/Cancel controls, and the backend only applies the update after confirmation
- Added backend validation for ownership, locked items, time format, start/end ordering, and same-day time conflicts
- Confirmed time edits now update the affected card immediately in the frontend and then refresh the plan in the background
- Implemented delete item skill through chat, including support for deleting one or multiple attractions/restaurants after confirmation
- Delete actions validate ownership and locked status before removing items, then immediately remove the cards from the page

**Assistant Architecture Refactor**
- Moved chat assistant logic out of `main.py` and `ai_service.py` into a dedicated `backend/trip_assistant/` package
- Added `trip_assistant/schemas.py` for chat request/action models
- Added `trip_assistant/prompts.py` for the structured assistant prompt
- Added `trip_assistant/service.py` for loading trip context, calling the LLM, parsing actions, and routing execution
- Added skill modules under `trip_assistant/skills/`: `edit_item_time.py` and `delete_items.py`
- `main.py` now keeps only thin route handlers for chat and chat action execution

**Scheduling Fix**
- Removed LLM-side conflict guessing for time edits
- Conflict detection is now deterministic in backend service code and checks only the target item's actual day/date
- If a proposed time overlaps with another item on the same day, the assistant returns a conflict explanation and does not show a Confirm action

**Model Configuration**
- Centralized OpenAI model selection behind the `OPENAI_MODEL` environment variable while preserving `gpt-4o-mini` as the default


# 5/16/2026

Continued building out the AI Trip Assistant skill system. The chatbox now supports several more concrete trip-editing and trip-question workflows beyond the initial edit/delete MVP.

**New Chat Skills**
- Implemented `replace_item` skill: users can ask the assistant to replace an itinerary card with a new AI-generated alternative based on preferences like "cheaper restaurant", "something outdoors", or "family friendly"
- Implemented `add_attraction` skill: users can ask the assistant to generate and add a new attraction/activity to a specific trip day after confirmation
- Implemented `add_user_place` skill: users can provide a specific known place they already want to visit, and the assistant validates it with Google Places before inserting it into the plan
- Implemented `ask_weather` skill: users can ask about weather for a specific trip day/date; the assistant queries weather data and summarizes the day by time period when hourly data is available

**Assistant Skill Architecture**
- Added new skill modules under `backend/trip_assistant/skills/`: `replace_item.py`, `add_attraction.py`, `add_user_place.py`, and `ask_weather.py`
- Extended `trip_assistant/prompts.py` with structured action types for `replace_item`, `add_attraction`, `add_user_place`, and `ask_weather`
- Extended `trip_assistant/service.py` to route new actions to their corresponding skill handlers
- Added a fallback action-extraction pass so the assistant does not ask the user to confirm without returning an executable action payload
- Read-only skills such as weather return a direct answer and do not show Confirm/Cancel controls

**Weather Support**
- Added hourly weather forecast lookup in `weather_service.py`
- Weather skill now attempts to use hourly data for morning/midday/afternoon/evening summaries
- If forecast data is unavailable for the requested date, the assistant is expected to say so instead of inventing conditions

**Frontend Updates**
- Chat Confirm flow now handles newly inserted items as well as updated/deleted cards
- Added day-level DOM metadata so chat-created cards can be inserted into the correct day immediately
- New cards are inserted and sorted without requiring a full manual page refresh

**Reliability Fixes**
- Fixed a crash caused by `action: null` responses when checking for read-only weather actions
- Strengthened chat response parsing so malformed or non-dict LLM output still resolves to a stable `{ reply, action }` shape
- Adjusted replacement prompts so broad preferences such as "cheaper restaurant" are treated as sufficient and do not trigger unnecessary clarification questions

**Planning**
- LangGraph is not introduced yet; current skill routing remains simple enough for the existing service/skills structure
- Plan to consider LangGraph when moving into multi-step skills such as conflict resolution, moving items across days, weather-aware rescheduling, or full-day optimization

