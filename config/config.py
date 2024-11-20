import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    FLIGHT_API_KEY = os.getenv("FLIGHT_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    BASE_FLIGHT_API_URL = "https://api.example.com/flights"
    MEMORY_TYPE = "simple"
    
    # Add database configuration
    BASE_DIR = Path(__file__).parent.parent
    DATABASE_PATH = str(BASE_DIR / "data" / "travel2.sqlite")

    @staticmethod
    def validate():
        required_vars = ["GROQ_API_KEY", "TAVILY_API_KEY", "FLIGHT_API_KEY"]
        missing = [var for var in required_vars if not getattr(Config, var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
