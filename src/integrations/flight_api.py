import requests

def get_flight_data(api_key: str, flight_id: str) -> dict:
    url = f"https://api.flightdata.com/flights/{flight_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
