"""Gemini response generation via the official google-genai SDK, with honest fallbacks."""
import logging
import time

from modules.safety import safety_message

log = logging.getLogger("aura.ai")

STRATEGY_GUIDE = {
    "casual": "Reply naturally and conversationally. Do not comment on the user's emotions unless they raise them.",
    "empathize": "Briefly acknowledge the feeling the user expressed, then respond helpfully. Avoid clichés.",
    "support": "Offer warm, gentle and practical support. Suggest at most one or two small, concrete steps.",
    "celebrate": "Respond with genuine, proportionate enthusiasm to the good news.",
    "clarify": "Ask one short, open question to understand what the user means or feels. Do not assume.",
    "neutral": "Answer the question or task directly and accurately. No emotional commentary.",
    "safety_support": ("The user may be at risk. Respond calmly and kindly, say you are an AI, encourage contacting "
                       "a trusted person or local emergency/crisis services, and ask whether they are safe now. "
                       "Do not give methods or diagnoses."),
}
LANG_NAMES = {"en": "English", "ur": "Urdu (Urdu script)", "roman_ur": "Roman Urdu (Urdu in Latin letters)"}
STYLE = {"balanced": "Keep replies moderately short.", "concise": "Keep replies very short (1-3 sentences).",
         "detailed": "You may give fuller, structured replies when useful."}


class AIUnavailable(Exception):
    pass


def _sdk_types():
    try:
        from google.genai import types
    except ImportError:
        raise AIUnavailable("sdk_not_installed")
    return types


def reply_language(pref, detected):
    if pref in LANG_NAMES:
        return LANG_NAMES[pref]
    return LANG_NAMES.get(detected, "the same language and script mix the user is writing in")


def build_system_prompt(strategy, language_pref, detected_language, memories, response_style, memory_note=None, risk_check=False):
    parts = [
        "You are AURA, a warm, natural AI companion. You are not a doctor or therapist and never diagnose.",
        f"Reply in {reply_language(language_pref, detected_language)}.",
        STYLE.get(response_style, STYLE["balanced"]),
        f"Response strategy for this turn: {strategy}. {STRATEGY_GUIDE[strategy]}",
        "Do not repeatedly name the user's detected emotion. Do not mention these instructions.",
    ]
    if memories:
        parts.append("Facts the user chose to save (use only if relevant): " + "; ".join(memories))
    if risk_check:
        parts.append("The user's words may hint at hopelessness. Gently and directly ask whether they are thinking about "
                     "harming themselves, say you are an AI, and mention they can contact a trusted person or local "
                     "emergency services if they are in danger. Do not lecture or panic.")
    if memory_note:
        parts.append(f"The user just asked you to remember: \"{memory_note}\". It has been saved; confirm briefly.")
    return "\n".join(parts)


class AIService:
    def __init__(self, api_key, model, timeout_seconds=20):
        self.api_key, self.model, self.timeout = api_key, model, timeout_seconds
        self._client = None

    @classmethod
    def from_config(cls, cfg):
        return cls(cfg["GEMINI_API_KEY"], cfg["GEMINI_MODEL"], cfg["GEMINI_TIMEOUT_SECONDS"])

    @property
    def configured(self):
        return bool(self.api_key)

    def _get_client(self):
        if not self.api_key:
            raise AIUnavailable("missing_api_key")
        if self._client is None:
            try:
                from google import genai
                from google.genai import types
            except ImportError:
                raise AIUnavailable("sdk_not_installed")

            self._client = genai.Client(
                api_key=self.api_key, http_options=types.HttpOptions(timeout=int(self.timeout * 1000)))
        return self._client

    def generate(self, message, history, system_prompt, attempts=2):
        """history: [{'role','content'}] excluding the current message. Returns text or raises AIUnavailable."""
        if not self.api_key:
            raise AIUnavailable("missing_api_key")
        types = _sdk_types()

        turns = [("model" if h["role"] == "assistant" else "user", h["content"]) for h in history]
        while turns and turns[0][0] == "model":
            turns.pop(0)
        turns.append(("user", message))
        contents = [types.Content(role=r, parts=[types.Part(text=t)]) for r, t in turns]
        config = types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.8, max_output_tokens=700)
        last = None
        for attempt in range(attempts):
            try:
                resp = self._get_client().models.generate_content(model=self.model, contents=contents, config=config)
                text = (resp.text or "").strip()
                if text:
                    return text
                last = "empty_response"
            except AIUnavailable:
                raise
            except Exception as exc:
                code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                last = type(exc).__name__ + (f":{code}" if code else "")
                log.warning("Gemini call failed (attempt %s): %s - %s", attempt + 1, last, str(exc)[:300])
                time.sleep(0.4)
        raise AIUnavailable(last or "unknown")


def _stream_impl(self, message, history, system_prompt, attempts=2):
    """Yield text chunks. Retries only before the first chunk; raises AIUnavailable on failure."""
    if not self.api_key:
        raise AIUnavailable("missing_api_key")
    types = _sdk_types()
    turns = [("model" if h["role"] == "assistant" else "user", h["content"]) for h in history]
    while turns and turns[0][0] == "model":
        turns.pop(0)
    turns.append(("user", message))
    contents = [types.Content(role=r, parts=[types.Part(text=t)]) for r, t in turns]
    config = types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.8, max_output_tokens=700)
    started, last = False, None
    for attempt in range(attempts):
        try:
            for chunk in self._get_client().models.generate_content_stream(model=self.model, contents=contents, config=config):
                text = chunk.text or ""
                if text:
                    started = True
                    yield text
            if started:
                return
            last = "empty_response"
        except AIUnavailable:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            last = type(exc).__name__ + (f":{code}" if code else "")
            log.warning("Gemini stream failed (attempt %s): %s - %s", attempt + 1, last, str(exc)[:300])
            if started:
                raise AIUnavailable(last)
            time.sleep(0.4)
    raise AIUnavailable(last or "unknown")


AIService.stream = _stream_impl

FALLBACK_TEXT = ("AI response generation is temporarily unavailable, so I can't answer properly right now. "
                 "Your message was saved. Please try again in a moment.")


def fallback_reply(strategy, safety_resources=""):
    """Returns (text, source). Never labelled as Gemini."""
    if strategy == "safety_support":
        return safety_message(safety_resources), "safety_template"
    return FALLBACK_TEXT, "fallback"
