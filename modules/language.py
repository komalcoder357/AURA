"""Script / language detection for English, Urdu script and Roman Urdu.
Heuristic: Latin text with no Roman Urdu markers is treated as English."""
import re
import unicodedata

URDU_CHARS = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")
LATIN_CHARS = re.compile(r"[A-Za-z]")
WORD = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)

ROMAN_URDU_WORDS = {
    "hai", "hain", "hun", "hoon", "ho", "hu", "tha", "thi", "nahi", "nahin", "mujhe", "mujh", "mera", "meri",
    "mere", "main", "mein", "tum", "tumhe", "aap", "apka", "apki", "kya", "kyun", "kyu", "kaise", "kaisa",
    "bohat", "bohot", "bahut", "bahot", "acha", "accha", "achha", "theek", "thik", "aur", "ka", "ki", "ke",
    "ko", "se", "pe", "bhi", "lekin", "magar", "kar", "karna", "rahi", "raha", "rahe", "udaas", "udaasi",
    "khush", "gussa", "ghussa", "samajh", "aj", "aaj", "kal", "abhi", "yaar", "yar", "bas", "koi", "kuch",
    "sab", "hum", "wo", "woh", "ye", "yeh", "mat", "shukriya", "lagta", "lag", "batao", "bata", "karo",
    "pareshan", "dukh", "dukhi", "hua", "hui", "gaya", "gayi", "chahta", "chahti", "zindagi",
}
ENGLISH_WORDS = {
    "i", "you", "the", "is", "am", "are", "and", "to", "of", "a", "an", "in", "my", "me", "it", "this", "that",
    "so", "very", "feel", "feeling", "today", "what", "how", "why", "can", "please", "have", "has", "was",
    "with", "for", "not", "but", "just", "really", "about", "help", "want", "need", "like", "good", "bad",
}


def tokens(text):
    return WORD.findall(text.lower())


def detect_language(text):
    """Return {'code': en|ur|roman_ur|mixed|unknown, 'script': ...}."""
    urdu = len(URDU_CHARS.findall(text))
    latin = len(LATIN_CHARS.findall(text))
    if urdu == 0 and latin == 0:
        return {"code": "unknown", "script": "none"}
    if urdu and latin:
        return {"code": "ur" if urdu / (urdu + latin) > 0.8 else "mixed", "script": "mixed"}
    if urdu:
        return {"code": "ur", "script": "urdu"}
    words = tokens(text)
    ru = sum(1 for w in words if w in ROMAN_URDU_WORDS)
    en = sum(1 for w in words if w in ENGLISH_WORDS)
    if ru == 0:
        return {"code": "en", "script": "latin"}
    if en == 0 or ru >= en:
        return {"code": "roman_ur", "script": "latin"}
    return {"code": "mixed", "script": "latin"}


def normalize(text, code):
    """Light normalisation that keeps meaning: unicode form, whitespace, Urdu letter variants,
    and (Roman Urdu / English) lower-casing plus squeezing of stretched letters."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    if code in ("ur", "mixed"):
        text = text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9").replace("\u06d5", "\u06c1")
    if code in ("roman_ur", "en", "mixed"):
        text = re.sub(r"(.)\1{2,}", r"\1\1", text)
    if code == "roman_ur":
        text = text.lower()
    return text
