# Navora — AI Travel Planner

An AI-powered travel planning web app that generates personalized day-by-day itineraries using a multi-agent architecture. Users input their trip details and receive a structured itinerary with real attractions, restaurants, weather-aware scheduling, and optional hotel/flight recommendations.

**Demo Final(maybe): https://youtu.be/P0LSRbDRLUM?si=TwvT4s6xbjSxzEkd

**Demo (5/7/2026):** https://www.youtube.com/watch?v=wkLbbmDhoQw


---

## Features

- **AI Itinerary Generation** — GPT-4o-mini generates a structured day-by-day plan using real place data
- **Multi-Agent Pipeline** — Orchestrator coordinates Attraction, Food, and Weather agents in parallel
- **Real Place Data** — Google Places API (New) provides verified attraction and restaurant names, addresses, and ratings
- **Weather-Aware Scheduling** — Open-Meteo weather forecasts influence indoor/outdoor activity selection
- **Traveler Type Scheduling** — Speedrunning (4 attractions/day), Normal (2/day), Chill (1 afternoon/day)
- **Metro-Region Search** — Users with a car get attractions pulled from the full metro area, not just the city center
- **Hotel & Flight Recommendations** — AI-generated suggestions displayed at the bottom of the itinerary
- **Per-Card Editing** — Each itinerary item can be updated, replaced (AI regenerates one item), locked, unlocked, or deleted
- **User Auth** — JWT-based login/register; trips are scoped per user
- **Trip History** — Browse and revisit all past generated trips
- **City Autocomplete** — Departure and destination city inputs validate against real cities via Google Places

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Database | PostgreSQL + SQLAlchemy |
| AI | OpenAI API (gpt-4o-mini) |
| Places | Google Places API (New) — Text Search |
| Weather | Open-Meteo (free, no key required) |
| Auth | python-jose (JWT) + passlib (bcrypt) |
| Frontend | Vanilla HTML / CSS / JavaScript |

---

## Project Structure

```
Navora-AI/
├── backend/
│   ├── main.py                        # FastAPI app, all API endpoints
│   ├── database.py                    # SQLAlchemy session setup
│   ├── ai_service.py                  # OpenAI itinerary + item replacement prompts
│   ├── orchestrator_agent.py          # Coordinates all specialized agents
│   ├── attraction_agent.py            # Fetches real attractions via Google Places
│   ├── food_agent.py                  # Fetches real restaurants via Google Places
│   ├── weather_agent.py               # Fetches weather forecasts via Open-Meteo
│   ├── places_service.py              # Google Places API wrapper
│   ├── weather_service.py             # Open-Meteo API wrapper
│   ├── city_service.py                # City autocomplete via Google Places
│   ├── travel_recommendation_service.py  # AI hotel & flight recommendations
│   ├── auth_service.py                # JWT creation/decoding, bcrypt hashing
│   └── db/sql.txt                     # Database schema
├── frontend/
│   ├── index.html                     # Main trip creation + itinerary view
│   ├── history.html                   # Trip history page
│   ├── trip-detail.html               # Individual trip detail view
│   ├── login.html                     # Login page
│   ├── register.html                  # Register page
│   ├── script.js                      # Core itinerary logic and rendering
│   ├── auth.js                        # Auth functions + API_BASE
│   ├── autocomplete.js                # City autocomplete dropdown
│   └── style.css                      # Full design system
├── requirements.txt
├── devlog.md
└── issues.md
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/crazycat948/Navora-AI.git
cd Navora-AI
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r ../requirements.txt
```

Create a `.env` file inside `backend/`:

```
OPENAI_API_KEY=your_openai_api_key
GOOGLE_PLACES_API_KEY=your_google_places_api_key
DATABASE_URL=postgresql://user:password@localhost:5432/navora
SECRET_KEY=your_jwt_secret_key
```

Start the server:

```bash
uvicorn main:app --reload
```

Backend runs at `http://127.0.0.1:8000`.

### 3. Database

Run the schema in `backend/db/sql.txt` against your PostgreSQL instance to create all required tables.

### 4. Frontend

Open `frontend/index.html` directly in a browser, or serve via any static file server. The frontend connects to `http://127.0.0.1:8000` by default (configured in `auth.js`).

---

## Agent Architecture

```
User Request
     │
     ▼
Orchestrator Agent
     ├── Attraction Agent  →  Google Places (tourist attractions, metro or city-only)
     ├── Food Agent        →  Google Places (restaurants)
     └── Weather Agent     →  Open-Meteo (day-by-day forecast)
     │
     ▼
Itinerary Planner (GPT-4o-mini)
     └── Generates structured JSON itinerary using only agent-provided places
```

---

## Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login and receive JWT |
| POST | `/api/trips/create` | Create a new trip |
| POST | `/api/trips/{id}/generate-ai-itinerary` | Run full agent pipeline and generate itinerary |
| GET | `/api/trips/{id}` | Fetch trip detail (days, items, hotels, flights) |
| GET | `/api/trips` | Fetch current user's trip history |
| DELETE | `/api/trips/{id}` | Delete a trip |
| PATCH | `/api/itinerary-items/{id}` | Update time, notes, or locked status |
| POST | `/api/itinerary-items/{id}/replace` | AI-replace a single unlocked item |
| DELETE | `/api/itinerary-items/{id}` | Delete an unlocked item |
| POST | `/api/trips/{id}/travel-recommendations` | Generate hotel & flight suggestions |
| GET | `/api/cities/search?q=` | City autocomplete |
| GET | `/api/trips/{id}/weather` | Fetch weather for trip dates |
