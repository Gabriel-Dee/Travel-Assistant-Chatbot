from src.chatbot.tools import fetch_user_flight_information, search_flights

def test_fetch_user_flight_information():
    config = {"configurable": {"passenger_id": "3442 587242"}}
    result = fetch_user_flight_information(config)
    assert isinstance(result, list)
    assert len(result) > 0

def test_search_flights():
    result = search_flights(departure_airport="JFK", arrival_airport="LAX")
    assert isinstance(result, list)
    assert len(result) > 0
