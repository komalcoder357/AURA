import os
from dotenv import load_dotenv

load_dotenv()

THEMES = [
    ("baby-pink", "Baby Pink"),
    ("lavender", "Lavender"),
    ("mint", "Mint Green"),
    ("peach", "Peach"),
    ("sky", "Sky Pastel"),
    ("neutral", "Neutral Warm"),
]


def _float(name, default):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


class Config:
    # If SECRET_KEY is unset a random one is used: sessions then reset on every restart.
    SECRET_KEY = os.getenv("SECRET_KEY") or os.urandom(32).hex()
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///aura.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    WTF_CSRF_TIME_LIMIT = None

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    GEMINI_TIMEOUT_SECONDS = _float("GEMINI_TIMEOUT_SECONDS", 20)

    EMOTION_MODEL_EN = os.getenv("EMOTION_MODEL_EN", "j-hartmann/emotion-english-distilroberta-base")
    EMOTION_MODEL_MULTI = os.getenv("EMOTION_MODEL_MULTI", "")
    EMOTION_LOAD = os.getenv("EMOTION_LOAD", "startup")
    EMOTION_MIN_CONFIDENCE = _float("EMOTION_MIN_CONFIDENCE", 0.5)

    CONTEXT_MESSAGES = int(os.getenv("CONTEXT_MESSAGES", 10))
    MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", 4))
    MAX_CONTENT_LENGTH = 1024 * 1024
    MAX_AVATAR_BYTES = 300 * 1024
    MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", 2000))
    MAX_MEMORY_ITEMS = 100
    WELCOME_TEXT = os.getenv("WELCOME_TEXT", "Hi, I'm AURA. How are you feeling today?")
    SAFETY_RESOURCES = os.getenv("SAFETY_RESOURCES", "")
    TESTING = False
