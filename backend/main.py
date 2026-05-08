from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from database import SessionLocal, test_connection
from ai_service import test_openai_connection, generate_itinerary_json, replace_itinerary_item_json
from places_service import search_places
from attraction_agent import get_attraction_recommendations
from food_agent import get_food_recommendations
from weather_service import get_weather_forecast
from weather_agent import get_weather_recommendations
from orchestrator_agent import run_orchestrator
from auth_service import hash_password, verify_password, create_access_token, decode_access_token

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserRegister(BaseModel):
    email: str
    password: str
    username: str


class UserLogin(BaseModel):
    email: str
    password: str


class TripCreate(BaseModel):
    title: str
    destination_city: str
    departure_city: str
    arrival_date: str
    departure_date: str
    traveler_type: str
    budget: int
    has_car: bool
    need_hotel: bool
    need_flight: bool


class ItineraryItemUpdate(BaseModel):
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    locked: Optional[bool] = None


def get_current_user_id(authorization: str):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        token_type, token = authorization.split(" ")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    if token_type.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid token type")

    payload = decode_access_token(token)

    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload["user_id"]


@app.post("/api/auth/register")
def register_user(user: UserRegister):
    db = SessionLocal()

    existing_user = db.execute(text("""
        SELECT *
        FROM users
        WHERE email = :email;
    """), {"email": user.email}).mappings().fetchone()

    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    password_hash = hash_password(user.password)

    result = db.execute(text("""
        INSERT INTO users (email, password_hash, username)
        VALUES (:email, :password_hash, :username)
        RETURNING id, email, username, created_at;
    """), {
        "email": user.email,
        "password_hash": password_hash,
        "username": user.username
    })

    new_user = result.mappings().fetchone()

    db.commit()
    db.close()

    token = create_access_token({
        "user_id": new_user["id"],
        "email": new_user["email"]
    })

    return {
        "message": "User registered successfully",
        "access_token": token,
        "token_type": "bearer",
        "user": dict(new_user)
    }


@app.post("/api/auth/login")
def login_user(user: UserLogin):
    db = SessionLocal()

    existing_user = db.execute(text("""
        SELECT *
        FROM users
        WHERE email = :email;
    """), {"email": user.email}).mappings().fetchone()

    db.close()

    if not existing_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(user.password, existing_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({
        "user_id": existing_user["id"],
        "email": existing_user["email"]
    })

    return {
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": existing_user["id"],
            "email": existing_user["email"],
            "username": existing_user["username"]
        }
    }


@app.get("/")
def root():
    return {"message": "AI Travel Planner Backend is running"}


@app.get("/db-test")
def db_test():
    result = test_connection()
    return {"database": "connected", "test_result": result}


@app.get("/openai-test")
def openai_test():
    result = test_openai_connection()
    return {"message": result}


@app.post("/api/trips/create")
def create_trip(trip: TripCreate, Authorization: str = Header(None)):
    user_id = get_current_user_id(Authorization)
    db = SessionLocal()

    query = text("""
        INSERT INTO trips (
            user_id,
            title,
            destination_city,
            departure_city,
            arrival_date,
            departure_date,
            traveler_type,
            budget,
            has_car,
            need_hotel,
            need_flight
        )
        VALUES (
            :user_id,
            :title,
            :destination_city,
            :departure_city,
            :arrival_date,
            :departure_date,
            :traveler_type,
            :budget,
            :has_car,
            :need_hotel,
            :need_flight
        )
        RETURNING id;
    """)

    result = db.execute(query, {
        "user_id": user_id,
        "title": trip.title,
        "destination_city": trip.destination_city,
        "departure_city": trip.departure_city,
        "arrival_date": trip.arrival_date,
        "departure_date": trip.departure_date,
        "traveler_type": trip.traveler_type,
        "budget": trip.budget,
        "has_car": trip.has_car,
        "need_hotel": trip.need_hotel,
        "need_flight": trip.need_flight
    })

    trip_id = result.fetchone()[0]
    db.commit()
    db.close()

    return {
        "message": "Trip created successfully",
        "trip_id": trip_id
    }


@app.post("/api/trips/{trip_id}/generate-itinerary")
def generate_itinerary(trip_id: int):
    db = SessionLocal()

    # 1. Create Day 1
    day_query = text("""
        INSERT INTO itinerary_days (trip_id, date, day_number, theme, notes)
        VALUES (:trip_id, '2026-06-01', 1, 'Arrival and City Highlights', 'Mock itinerary for testing')
        RETURNING id;
    """)

    day_result = db.execute(day_query, {"trip_id": trip_id})
    day_id = day_result.fetchone()[0]

    # 2. Mock itinerary items
    items = [
        {
            "item_type": "attraction",
            "start_time": "09:00",
            "end_time": "11:00",
            "name": "Griffith Observatory",
            "address": "2800 E Observatory Rd, Los Angeles, CA",
            "notes": "Great city view and photo spot.",
            "source_agent": "Attraction Agent",
            "source_api": "Mock Data",
            "order_index": 1
        },
        {
            "item_type": "restaurant",
            "start_time": "12:00",
            "end_time": "13:00",
            "name": "In-N-Out Burger",
            "address": "7009 Sunset Blvd, Los Angeles, CA",
            "notes": "Casual lunch option.",
            "source_agent": "Food Agent",
            "source_api": "Mock Data",
            "order_index": 2
        },
        {
            "item_type": "attraction",
            "start_time": "14:00",
            "end_time": "16:00",
            "name": "Hollywood Walk of Fame",
            "address": "Hollywood Blvd, Los Angeles, CA",
            "notes": "Classic LA landmark.",
            "source_agent": "Attraction Agent",
            "source_api": "Mock Data",
            "order_index": 3
        }
    ]

    # 3. Insert itinerary items
    for item in items:
        item_query = text("""
            INSERT INTO itinerary_items (
                trip_id,
                day_id,
                item_type,
                start_time,
                end_time,
                name,
                address,
                notes,
                source_agent,
                source_api,
                order_index
            )
            VALUES (
                :trip_id,
                :day_id,
                :item_type,
                :start_time,
                :end_time,
                :name,
                :address,
                :notes,
                :source_agent,
                :source_api,
                :order_index
            );
        """)

        db.execute(item_query, {
            "trip_id": trip_id,
            "day_id": day_id,
            **item
        })

    db.commit()
    db.close()

    return {
        "message": "Mock itinerary generated successfully",
        "trip_id": trip_id,
        "day_id": day_id,
        "items_created": len(items)
    }

@app.get("/api/trips/{trip_id}")
def get_trip_detail(trip_id: int):
    db = SessionLocal()

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": trip_id}).mappings().fetchone()

    if not trip:
        db.close()
        return {"error": "Trip not found"}

    days = db.execute(text("""
        SELECT *
        FROM itinerary_days
        WHERE trip_id = :trip_id
        ORDER BY day_number;
    """), {"trip_id": trip_id}).mappings().fetchall()

    result_days = []

    for day in days:
        items = db.execute(text("""
            SELECT *
            FROM itinerary_items
            WHERE day_id = :day_id
            ORDER BY order_index;
        """), {"day_id": day["id"]}).mappings().fetchall()

        result_days.append({
            "id": day["id"],
            "date": str(day["date"]),
            "day_number": day["day_number"],
            "theme": day["theme"],
            "notes": day["notes"],
            "items": [dict(item) for item in items]
        })

    db.close()

    return {
        "trip": dict(trip),
        "days": result_days
    }

@app.get("/api/trips")
def get_trip_history(authorization: str = Header(None)):
    user_id = get_current_user_id(authorization)

    db = SessionLocal()

    trips = db.execute(text("""
        SELECT *
        FROM trips
        WHERE user_id = :user_id
        ORDER BY created_at DESC;
    """), {
        "user_id": user_id
    }).mappings().fetchall()

    db.close()

    return {
        "trips": [dict(trip) for trip in trips]
    }

@app.get("/api/trips/{trip_id}/ai-preview")
def ai_preview(trip_id: int):
    db = SessionLocal()

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": trip_id}).mappings().fetchone()

    db.close()

    if not trip:
        return {"error": "Trip not found"}

    itinerary_json = generate_itinerary_json(dict(trip))

    return itinerary_json

@app.post("/api/trips/{trip_id}/generate-ai-itinerary")
def generate_ai_itinerary(trip_id: int):
    db = SessionLocal()

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": trip_id}).mappings().fetchone()

    if not trip:
        db.close()
        return {"error": "Trip not found"}

    db.execute(text("""
        DELETE FROM itinerary_items
        WHERE trip_id = :trip_id;
    """), {"trip_id": trip_id})

    db.execute(text("""
        DELETE FROM itinerary_days
        WHERE trip_id = :trip_id;
    """), {"trip_id": trip_id})

    orchestrator_result = run_orchestrator(dict(trip))

    agent_outputs = orchestrator_result["agent_outputs"]

    itinerary_json = generate_itinerary_json(
        dict(trip),
        attraction_data=agent_outputs["attractions"],
        food_data=agent_outputs["foods"],
        weather_data=agent_outputs["weather"]
    )

    days_created = 0
    items_created = 0

    for day in itinerary_json["days"]:
        day_result = db.execute(text("""
            INSERT INTO itinerary_days (trip_id, date, day_number, theme, notes)
            VALUES (:trip_id, :date, :day_number, :theme, :notes)
            RETURNING id;
        """), {
            "trip_id": trip_id,
            "date": day["date"],
            "day_number": day["day_number"],
            "theme": day["theme"],
            "notes": day["notes"]
        })

        day_id = day_result.fetchone()[0]
        days_created += 1

        for index, item in enumerate(day["items"], start=1):
            db.execute(text("""
                INSERT INTO itinerary_items (
                    trip_id,
                    day_id,
                    item_type,
                    start_time,
                    end_time,
                    name,
                    address,
                    notes,
                    source_agent,
                    source_api,
                    external_place_id,
                    order_index
                )
                VALUES (
                    :trip_id,
                    :day_id,
                    :item_type,
                    :start_time,
                    :end_time,
                    :name,
                    :address,
                    :notes,
                    :source_agent,
                    :source_api,
                    :external_place_id,
                    :order_index
                );
            """), {
                "trip_id": trip_id,
                "day_id": day_id,
                "item_type": item["item_type"],
                "start_time": item["start_time"],
                "end_time": item["end_time"],
                "name": item["name"],
                "address": item["address"],
                "notes": item["notes"],
                "source_agent": item["source_agent"],
                "source_api": item["source_api"],
                "external_place_id": item.get("external_place_id"),
                "order_index": index
            })

            items_created += 1

    db.commit()
    db.close()

    return {
        "message": "AI itinerary generated and saved successfully",
        "trip_id": trip_id,
        "days_created": days_created,
        "items_created": items_created
    }


@app.patch("/api/itinerary-items/{item_id}")
def update_itinerary_item(item_id: int, update: ItineraryItemUpdate):
    db = SessionLocal()

    existing_item = db.execute(text("""
        SELECT *
        FROM itinerary_items
        WHERE id = :item_id;
    """), {"item_id": item_id}).mappings().fetchone()

    if not existing_item:
        db.close()
        return {"error": "Itinerary item not found"}

    update_data = update.model_dump(exclude_unset=True)

    if not update_data:
        db.close()
        return {"error": "No fields provided for update"}

    set_clauses = []
    params = {"item_id": item_id}

    for field, value in update_data.items():
        set_clauses.append(f"{field} = :{field}")
        params[field] = value

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")

    query = text(f"""
        UPDATE itinerary_items
        SET {", ".join(set_clauses)}
        WHERE id = :item_id
        RETURNING *;
    """)

    updated_item = db.execute(query, params).mappings().fetchone()

    db.commit()
    db.close()

    return {
        "message": "Itinerary item updated successfully",
        "item": dict(updated_item)
    }


@app.post("/api/itinerary-items/{item_id}/replace")
def replace_itinerary_item(item_id: int):
    db = SessionLocal()

    current_item = db.execute(text("""
        SELECT *
        FROM itinerary_items
        WHERE id = :item_id;
    """), {"item_id": item_id}).mappings().fetchone()

    if not current_item:
        db.close()
        return {"error": "Itinerary item not found"}

    if current_item["locked"]:
        db.close()
        return {"error": "This item is locked and cannot be replaced"}

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": current_item["trip_id"]}).mappings().fetchone()

    if not trip:
        db.close()
        return {"error": "Trip not found"}

    existing_items = db.execute(text("""
        SELECT name
        FROM itinerary_items
        WHERE day_id = :day_id
          AND id != :item_id;
    """), {
        "day_id": current_item["day_id"],
        "item_id": item_id
    }).fetchall()

    existing_names = [row[0] for row in existing_items]

    new_item = replace_itinerary_item_json(dict(trip), dict(current_item), existing_names)

    updated_item = db.execute(text("""
        UPDATE itinerary_items
        SET
            item_type = :item_type,
            start_time = :start_time,
            end_time = :end_time,
            name = :name,
            address = :address,
            notes = :notes,
            source_agent = :source_agent,
            source_api = :source_api,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = :item_id
        RETURNING *;
    """), {
        "item_id": item_id,
        "item_type": new_item["item_type"],
        "start_time": new_item["start_time"],
        "end_time": new_item["end_time"],
        "name": new_item["name"],
        "address": new_item["address"],
        "notes": new_item["notes"],
        "source_agent": new_item["source_agent"],
        "source_api": new_item["source_api"]
    }).mappings().fetchone()

    db.commit()
    db.close()

    return {
        "message": "Itinerary item replaced successfully",
        "item": dict(updated_item)
    }

@app.get("/api/trips/{trip_id}/orchestrator-test")
def orchestrator_test(trip_id: int):
    db = SessionLocal()

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": trip_id}).mappings().fetchone()

    db.close()

    if not trip:
        return {"error": "Trip not found"}

    return run_orchestrator(dict(trip))


@app.delete("/api/trips/{trip_id}")
def delete_trip(trip_id: int, authorization: str = Header(None)):
    user_id = get_current_user_id(authorization)

    db = SessionLocal()

    existing_trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id
          AND user_id = :user_id;
    """), {
        "trip_id": trip_id,
        "user_id": user_id
    }).mappings().fetchone()

    if not existing_trip:
        db.close()
        raise HTTPException(status_code=404, detail="Trip not found")

    db.execute(text("""
        DELETE FROM itinerary_items
        WHERE trip_id = :trip_id;
    """), {"trip_id": trip_id})

    db.execute(text("""
        DELETE FROM itinerary_days
        WHERE trip_id = :trip_id;
    """), {"trip_id": trip_id})

    db.execute(text("""
        DELETE FROM trips
        WHERE id = :trip_id
          AND user_id = :user_id;
    """), {
        "trip_id": trip_id,
        "user_id": user_id
    })

    db.commit()
    db.close()

    return {
        "message": "Trip deleted successfully",
        "deleted_trip_id": trip_id
    }


@app.delete("/api/itinerary-items/{item_id}")
def delete_itinerary_item(item_id: int):
    db = SessionLocal()

    existing_item = db.execute(text("""
        SELECT *
        FROM itinerary_items
        WHERE id = :item_id;
    """), {"item_id": item_id}).mappings().fetchone()

    if not existing_item:
        db.close()
        return {"error": "Itinerary item not found"}

    db.execute(text("""
        DELETE FROM itinerary_items
        WHERE id = :item_id;
    """), {"item_id": item_id})

    db.commit()
    db.close()

    return {
        "message": "Itinerary item deleted successfully",
        "deleted_item_id": item_id
    }


@app.get("/places-test")
def places_test():
    return search_places(
        query="tourist attractions",
        location="Los Angeles"
    )


@app.get("/api/trips/{trip_id}/attractions")
def get_trip_attractions(trip_id: int):
    db = SessionLocal()

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": trip_id}).mappings().fetchone()

    db.close()

    if not trip:
        return {"error": "Trip not found"}

    return get_attraction_recommendations(dict(trip))


@app.get("/api/trips/{trip_id}/foods")
def get_trip_foods(trip_id: int):
    db = SessionLocal()

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": trip_id}).mappings().fetchone()

    db.close()

    if not trip:
        return {"error": "Trip not found"}

    return get_food_recommendations(dict(trip))


@app.get("/weather-test")
def weather_test():
    return get_weather_forecast(
        latitude=34.0522,
        longitude=-118.2437,
        days=5
    )


@app.get("/api/trips/{trip_id}/weather")
def get_trip_weather(trip_id: int):
    db = SessionLocal()

    trip = db.execute(text("""
        SELECT *
        FROM trips
        WHERE id = :trip_id;
    """), {"trip_id": trip_id}).mappings().fetchone()

    db.close()

    if not trip:
        return {"error": "Trip not found"}

    return get_weather_recommendations(dict(trip))