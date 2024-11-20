from pydantic import BaseModel, Field

class FlightBookingRequest(BaseModel):
    passenger_id: str = Field(..., description="The ID of the passenger")
    flight_id: str = Field(..., description="The ID of the flight")
