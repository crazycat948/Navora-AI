from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text
from database import SessionLocal, test_connection

app = FastAPI()


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


@app.get("/")
def root():
    return {"message": "AI Travel Planner Backend is running"}


@app.get("/db-test")
def db_test():
    result = test_connection()
    return {"database": "connected", "test_result": result}


@app.post("/api/trips/create")
def create_trip(trip: TripCreate):
    db = SessionLocal()

    query = text("""
        INSERT INTO trips (
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