"""Run: python check_gemini.py   -> prints the real reason Gemini calls fail."""
import sys
from config import Config

print("Model:", Config.GEMINI_MODEL)
print("API key set:", bool(Config.GEMINI_API_KEY))
if not Config.GEMINI_API_KEY:
    sys.exit("GEMINI_API_KEY is empty. Put it in .env (same folder as app.py) and run again.")
try:
    from google import genai
except ImportError:
    sys.exit("google-genai is not installed. Run: pip install google-genai")
try:
    client = genai.Client(api_key=Config.GEMINI_API_KEY)
    resp = client.models.generate_content(model=Config.GEMINI_MODEL, contents="Say hi in one short sentence.")
    print("OK ->", resp.text)
except Exception as exc:
    print("FAILED:", type(exc).__name__, getattr(exc, "code", ""), "\n", exc)
    print("\nTip: to list models your key can use, run:\n"
          "python -c \"from google import genai; import config; "
          "[print(m.name) for m in genai.Client(api_key=config.Config.GEMINI_API_KEY).models.list()]\"")
