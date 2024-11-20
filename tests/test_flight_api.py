from src.integrations.flight_api import get_flight_data

def test_get_flight_data():
    api_key = "your_api_key"
    flight_id = "12345"
    result = get_flight_data(api_key, flight_id)
    assert isinstance(result, dict)
    assert "flight_id" in result
