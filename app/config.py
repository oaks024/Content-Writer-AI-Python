"""Environment configuration."""
import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
PORT: int = int(os.getenv("PORT", "8000"))


def has_api_key() -> bool:
    """True when a non-empty Groq API key is configured."""
    return bool(GROQ_API_KEY)
