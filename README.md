# Travel Assistant Chatbot

This project is a travel assistant chatbot built using LangChain and FastAPI.

## Setup

1. Clone the repository.
2. Install the dependencies using `pip install -r requirements.txt`.
3. Set up the environment variables in the `.env` file.
4. Run the application using `uvicorn src.app:app --reload`.

## Folder Structure

- `config/`: Configuration files.
- `src/`: Source code.
  - `chatbot/`: Chatbot-specific code.
  - `integrations/`: Third-party integrations.
  - `utils/`: Helper functions and utilities.
- `tests/`: Test suite.
- `deployment/`: Deployment scripts.

## Installation

1. Clone the repository:
```git clone https://github.com/yourusername/travel-assistant-chatbot.git cd travel-assistant-chatbot```

2. Install dependencies:
```pip install -r requirements.txt```

3. Add environment variables to `.env`:
```OPENAI_API_KEY=your_openai_key FLIGHT_API_KEY=your_flight_api_key```

4. Run the application:
```uvicorn src.app:app--reload```

5. Access the API at `http://127.0.0.1:8000/docs`.

## Database Setup

The application uses a SQLite database containing flight and booking information. The database will be automatically downloaded and initialized when you first run the application. A backup copy is also created for development purposes.

The database contains the following tables:

- flights: Flight information
- bookings: Booking records
- tickets: Ticket information
- boarding_passes: Boarding pass details

## User Interactions

The chatbot implements a confirmation system for actions:

- Before executing any tool (like booking flights or hotels), the system will ask for user confirmation
- Users can approve actions by typing 'y'
- Users can deny actions and provide alternative instructions
- This ensures user control over all significant actions
