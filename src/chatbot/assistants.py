from pydantic import BaseModel, Field

class ToFlightBookingAssistant(BaseModel):
    request: str = Field(description="Followup questions for flight updates.")

class ToBookCarRental(BaseModel):
    location: str = Field(description="Car rental location")
    start_date: str = Field(description="Rental start date")
    end_date: str = Field(description="Rental end date")
    request: str = Field(description="Additional rental requests")

class ToHotelBookingAssistant(BaseModel):
    location: str = Field(description="Hotel location")
    checkin_date: str = Field(description="Check-in date")
    checkout_date: str = Field(description="Check-out date")
    request: str = Field(description="Additional hotel requests")

class ToBookExcursion(BaseModel):
    location: str = Field(description="Excursion location")
    request: str = Field(description="Additional excursion requests")