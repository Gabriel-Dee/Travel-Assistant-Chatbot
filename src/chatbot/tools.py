from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda
import sqlite3
from datetime import date, datetime
from typing import Optional, Union
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
import pytz
from config.config import Config
import uuid
from pydantic import BaseModel, Field

db = Config.DATABASE_PATH


@tool
def fetch_user_flight_information(config: RunnableConfig) -> list[dict]:
    """
    Fetch flight information for a specific user based on their passenger ID.
    
    Args:
        config (RunnableConfig): Configuration object containing passenger_id in configurable field.
        
    Returns:
        list[dict]: List of flight information dictionaries for the user.
    """
    configuration = config.get("configurable", {})
    passenger_id = configuration.get("passenger_id", None)
    if not passenger_id:
        raise ValueError("No passenger ID configured.")

    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    query = """
    SELECT
        t.ticket_no, t.book_ref,
        f.flight_id, f.flight_no, f.departure_airport, f.arrival_airport, f.scheduled_departure, f.scheduled_arrival,
        bp.seat_no, tf.fare_conditions
    FROM
        tickets t
        JOIN ticket_flights tf ON t.ticket_no = tf.ticket_no
        JOIN flights f ON tf.flight_id = f.flight_id
        JOIN boarding_passes bp ON bp.ticket_no = t.ticket_no AND bp.flight_id = f.flight_id
    WHERE
        t.passenger_id = ?
    """
    cursor.execute(query, (passenger_id,))
    rows = cursor.fetchall()
    column_names = [column[0] for column in cursor.description]
    results = [dict(zip(column_names, row)) for row in rows]

    cursor.close()
    conn.close()

    return results


@tool
def search_flights(
    departure_airport: Optional[str] = None,
    arrival_airport: Optional[str] = None,
    start_time: Optional[date | datetime] = None,
    end_time: Optional[date | datetime] = None,
    limit: int = 20,
) -> list[dict]:
    """
    Search for available flights based on specified criteria.
    
    Args:
        departure_airport (str, optional): Departure airport code
        arrival_airport (str, optional): Arrival airport code
        start_time (date | datetime, optional): Earliest departure time
        end_time (date | datetime, optional): Latest departure time
        limit (int, optional): Maximum number of results to return
        
    Returns:
        list[dict]: List of matching flight information
    """
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    query = "SELECT * FROM flights WHERE 1 = 1"
    params = []

    if departure_airport:
        query += " AND departure_airport = ?"
        params.append(departure_airport)

    if arrival_airport:
        query += " AND arrival_airport = ?"
        params.append(arrival_airport)

    if start_time:
        query += " AND scheduled_departure >= ?"
        params.append(start_time)

    if end_time:
        query += " AND scheduled_departure <= ?"
        params.append(end_time)
    query += " LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    column_names = [column[0] for column in cursor.description]
    results = [dict(zip(column_names, row)) for row in rows]

    cursor.close()
    conn.close()

    return results


@tool
def update_ticket_to_new_flight(
    ticket_no: str, new_flight_id: int, *, config: RunnableConfig
) -> str:
    """
    Update an existing ticket to a different flight.
    
    Args:
        ticket_no (str): The ticket number to update
        new_flight_id (int): The ID of the new flight
        config (RunnableConfig): Configuration object containing passenger_id
        
    Returns:
        str: Status message indicating success or failure
    """
    configuration = config.get("configurable", {})
    passenger_id = configuration.get("passenger_id", None)
    if not passenger_id:
        raise ValueError("No passenger ID configured.")

    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT departure_airport, arrival_airport, scheduled_departure FROM flights WHERE flight_id = ?",
        (new_flight_id,),
    )
    new_flight = cursor.fetchone()
    if not new_flight:
        cursor.close()
        conn.close()
        return "Invalid new flight ID provided."
    column_names = [column[0] for column in cursor.description]
    new_flight_dict = dict(zip(column_names, new_flight))
    timezone = pytz.timezone("Etc/GMT-3")
    current_time = datetime.now(tz=timezone)
    departure_time = datetime.strptime(
        new_flight_dict["scheduled_departure"], "%Y-%m-%d %H:%M:%S.%f%z"
    )
    time_until = (departure_time - current_time).total_seconds()
    if time_until < (3 * 3600):
        return f"Not permitted to reschedule to a flight that is less than 3 hours from the current time. Selected flight is at {departure_time}."

    cursor.execute(
        "SELECT flight_id FROM ticket_flights WHERE ticket_no = ?", (
            ticket_no,)
    )
    current_flight = cursor.fetchone()
    if not current_flight:
        cursor.close()
        conn.close()
        return "No existing ticket found for the given ticket number."

    cursor.execute(
        "SELECT * FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
        (ticket_no, passenger_id),
    )
    current_ticket = cursor.fetchone()
    if not current_ticket:
        cursor.close()
        conn.close()
        return f"Current signed-in passenger with ID {passenger_id} not the owner of ticket {ticket_no}"

    cursor.execute(
        "UPDATE ticket_flights SET flight_id = ? WHERE ticket_no = ?",
        (new_flight_id, ticket_no),
    )
    conn.commit()

    cursor.close()
    conn.close()
    return "Ticket successfully updated to new flight."


@tool
def cancel_ticket(ticket_no: str, *, config: RunnableConfig) -> str:
    """
    Cancel an existing flight ticket.
    
    Args:
        ticket_no (str): The ticket number to cancel
        config (RunnableConfig): Configuration object containing passenger_id
        
    Returns:
        str: Status message indicating success or failure
    """
    configuration = config.get("configurable", {})
    passenger_id = configuration.get("passenger_id", None)
    if not passenger_id:
        raise ValueError("No passenger ID configured.")
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT flight_id FROM ticket_flights WHERE ticket_no = ?", (
            ticket_no,)
    )
    existing_ticket = cursor.fetchone()
    if not existing_ticket:
        cursor.close()
        conn.close()
        return "No existing ticket found for the given ticket number."

    cursor.execute(
        "SELECT flight_id FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
        (ticket_no, passenger_id),
    )
    current_ticket = cursor.fetchone()
    if not current_ticket:
        cursor.close()
        conn.close()
        return f"Current signed-in passenger with ID {passenger_id} not the owner of ticket {ticket_no}"

    cursor.execute(
        "DELETE FROM ticket_flights WHERE ticket_no = ?", (ticket_no,))
    conn.commit()

    cursor.close()
    conn.close()
    return "Ticket successfully cancelled."


@tool
def lookup_policy(query: str) -> str:
    """
    Look up Swiss Airlines policy information based on a query.
    
    Args:
        query (str): The policy-related question or keyword to search for
        
    Returns:
        str: Relevant policy information
    """
    policies = {
        "baggage": "Swiss Airlines allows one carry-on bag and one personal item for free. Checked baggage allowance varies by ticket class.",
        "cancellation": "Tickets can be cancelled up to 24 hours before departure. Refund amount depends on fare type.",
        "changes": "Flight changes are permitted up to 3 hours before departure, subject to fare difference and change fee.",
        "pets": "Small pets in carriers are allowed in cabin. Larger animals must travel in cargo hold.",
        "check-in": "Online check-in opens 24 hours before departure and closes 4 hours before flight time.",
        "meals": "Complimentary meals and beverages are provided on most flights over 4 hours.",
        "default": "Please specify what policy information you're looking for (e.g., baggage, cancellation, changes, pets, check-in, or meals)."
    }
    
    query = query.lower()
    for key, value in policies.items():
        if key in query:
            return value
    return policies["default"]


@tool
def search_car_rentals(
    location: Optional[str] = None,
    name: Optional[str] = None,
    price_tier: Optional[str] = None,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
) -> list[dict]:
    """Search for car rentals based on location, name, price tier, and dates."""
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    query = "SELECT * FROM car_rentals WHERE 1=1"
    params = []

    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return [dict(zip([column[0] for column in cursor.description], row)) 
            for row in results]


@tool
def book_car_rental(rental_id: int) -> str:
    """Book a car rental by its ID."""
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("UPDATE car_rentals SET booked = 1 WHERE id = ?", (rental_id,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return f"Car rental {rental_id} {'successfully booked' if success else 'not found'}"


@tool
def search_hotels(
    location: Optional[str] = None,
    name: Optional[str] = None,
    price_tier: Optional[str] = None,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
) -> list[dict]:
    """Search for hotels based on criteria."""
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    query = "SELECT * FROM hotels WHERE 1=1"
    params = []
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return [dict(zip([column[0] for column in cursor.description], row)) 
            for row in results]


@tool
def search_trip_recommendations(
    location: Optional[str] = None,
    name: Optional[str] = None,
    keywords: Optional[str] = None,
) -> list[dict]:
    """Search for trip recommendations."""
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    query = "SELECT * FROM trip_recommendations WHERE 1=1"
    params = []
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")
    if keywords:
        keyword_list = keywords.split(",")
        keyword_conditions = " OR ".join(["keywords LIKE ?" for _ in keyword_list])
        query += f" AND ({keyword_conditions})"
        params.extend([f"%{keyword.strip()}%" for keyword in keyword_list])
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return [dict(zip([column[0] for column in cursor.description], row)) 
            for row in results]


@tool
def search_hotels(location: str, check_in: str, check_out: str, guests: int = 1) -> list:
    """
    Search for available hotels in a specific location.
    
    Args:
        location (str): City or area to search for hotels
        check_in (str): Check-in date (YYYY-MM-DD format)
        check_out (str): Check-out date (YYYY-MM-DD format)
        guests (int): Number of guests
        
    Returns:
        list: List of available hotels with details
    """
    # Simulated hotel data
    hotels = [
        {
            "id": "HTL001",
            "name": "Grand Hotel Central",
            "location": location,
            "price_per_night": 200,
            "rating": 4.5,
            "available_rooms": 5
        },
        {
            "id": "HTL002",
            "name": "Comfort Inn Express",
            "location": location,
            "price_per_night": 150,
            "rating": 4.0,
            "available_rooms": 8
        },
        {
            "id": "HTL003",
            "name": "Luxury Plaza Hotel",
            "location": location,
            "price_per_night": 300,
            "rating": 4.8,
            "available_rooms": 3
        }
    ]
    return hotels


@tool
def book_hotel(hotel_id: str, check_in: str, check_out: str, guests: int = 1) -> dict:
    """
    Book a hotel room.
    
    Args:
        hotel_id (str): ID of the hotel to book
        check_in (str): Check-in date (YYYY-MM-DD format)
        check_out (str): Check-out date (YYYY-MM-DD format)
        guests (int): Number of guests
        
    Returns:
        dict: Booking confirmation details
    """
    # Simulated booking confirmation
    booking = {
        "booking_id": f"BK{uuid.uuid4().hex[:8]}",
        "hotel_id": hotel_id,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "status": "confirmed",
        "total_price": 200 * ((datetime.strptime(check_out, "%Y-%m-%d") - 
                              datetime.strptime(check_in, "%Y-%m-%d")).days)
    }
    return booking


@tool
def update_hotel(booking_id: str, check_in: str = None, check_out: str = None, guests: int = None) -> dict:
    """
    Update an existing hotel booking.
    
    Args:
        booking_id (str): ID of the booking to update
        check_in (str, optional): New check-in date (YYYY-MM-DD format)
        check_out (str, optional): New check-out date (YYYY-MM-DD format)
        guests (int, optional): New number of guests
        
    Returns:
        dict: Updated booking details
    """
    # Simulated booking update
    updated_booking = {
        "booking_id": booking_id,
        "status": "updated",
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "update_fee": 50
    }
    return updated_booking


@tool
def cancel_hotel(booking_id: str) -> dict:
    """
    Cancel a hotel booking.
    
    Args:
        booking_id (str): ID of the booking to cancel
        
    Returns:
        dict: Cancellation confirmation
    """
    # Simulated cancellation confirmation
    cancellation = {
        "booking_id": booking_id,
        "status": "cancelled",
        "refund_amount": 150,
        "cancellation_fee": 50
    }
    return cancellation


@tool
def book_excursion(excursion_id: str, date: str, participants: int = 1) -> dict:
    """
    Book an excursion or activity.
    
    Args:
        excursion_id (str): ID of the excursion to book
        date (str): Date of the excursion (YYYY-MM-DD format)
        participants (int): Number of participants
        
    Returns:
        dict: Booking confirmation details
    """
    # Simulated booking confirmation
    booking = {
        "booking_id": f"EX{uuid.uuid4().hex[:8]}",
        "excursion_id": excursion_id,
        "date": date,
        "participants": participants,
        "status": "confirmed",
        "total_price": 75 * participants
    }
    return booking


@tool
def update_excursion(booking_id: str, date: str = None, participants: int = None) -> dict:
    """
    Update an existing excursion booking.
    
    Args:
        booking_id (str): ID of the booking to update
        date (str, optional): New date (YYYY-MM-DD format)
        participants (int, optional): New number of participants
        
    Returns:
        dict: Updated booking details
    """
    # Simulated booking update
    updated_booking = {
        "booking_id": booking_id,
        "status": "updated",
        "date": date,
        "participants": participants,
        "update_fee": 10
    }
    return updated_booking


@tool
def cancel_excursion(booking_id: str) -> dict:
    """
    Cancel an excursion booking.
    
    Args:
        booking_id (str): ID of the booking to cancel
        
    Returns:
        dict: Cancellation confirmation
    """
    # Simulated cancellation confirmation
    cancellation = {
        "booking_id": booking_id,
        "status": "cancelled",
        "refund_amount": 60,
        "cancellation_fee": 15
    }
    return cancellation


@tool
def update_car_rental(booking_id: str, start_date: str = None, end_date: str = None) -> dict:
    """
    Update an existing car rental booking.
    
    Args:
        booking_id (str): ID of the booking to update
        start_date (str, optional): New start date (YYYY-MM-DD format)
        end_date (str, optional): New end date (YYYY-MM-DD format)
        
    Returns:
        dict: Updated booking details
    """
    # Simulated booking update
    updated_booking = {
        "booking_id": booking_id,
        "status": "updated",
        "start_date": start_date,
        "end_date": end_date,
        "update_fee": 25
    }
    return updated_booking


@tool
def cancel_car_rental(booking_id: str) -> dict:
    """
    Cancel a car rental booking.
    
    Args:
        booking_id (str): ID of the booking to cancel
        
    Returns:
        dict: Cancellation confirmation
    """
    # Simulated cancellation confirmation
    cancellation = {
        "booking_id": booking_id,
        "status": "cancelled",
        "refund_amount": 100,
        "cancellation_fee": 30
    }
    return cancellation


def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


class CompleteOrEscalate(BaseModel):
    """Tool to mark task completion or escalation."""
    cancel: bool = True
    reason: str

    class Config:
        json_schema_extra = {
            "example": {
                "cancel": True,
                "reason": "User changed their mind about the current task."
            }
        }
