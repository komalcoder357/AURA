"""Rule-based response-strategy selection. Pure function, no Gemini involved.
Every reason code corresponds to a rule that actually fired."""
import re

from modules.emotion import NEGATIVE, POSITIVE

TASK_RE = re.compile(
    r"^\s*(how|what|when|where|who|which|why|can you|could you|please|explain|write|give|tell me|define|"
    r"translate|fix|debug|kya|kaise|kyun|kon|batao|bata do|samjhao)\b", re.IGNORECASE)
FEELING_RE = re.compile(r"\b(i feel|i am|i'm|im|i was|am i|why do i|mujhe|main|mera|meri|mere)\b", re.IGNORECASE)
STRONG = 0.85
GOOD = 0.7


def looks_like_task(text):
    return bool(TASK_RE.match(text)) and not FEELING_RE.search(text)


def decide(message, emotion, safety, distress=None, min_confidence=0.5):
    reasons = []

    def out(strategy, confidence=None):
        return {"strategy": strategy, "reason_codes": reasons, "confidence": confidence}

    if safety and safety.get("flag"):
        level = safety.get("level") or "high"
        reasons.append("safety_language_detected" if level == "high" else "possible_risk_indirect")
        result = out("safety_support", 1.0)
        result["safety_level"] = level
        return result

    if safety and safety.get("level") == "possible":
        reasons.append("indirect_risk_language")
        return out("support", 0.8)

    if looks_like_task(message):
        reasons.append("task_request")
        return out("neutral")

    label = emotion.get("emotion")
    status = emotion.get("analysis_status")
    conf = emotion.get("emotion_confidence")

    if not label or status not in ("success", "uncertain", "experimental"):
        reasons.append("no_reliable_emotion_signal")
        if len(message.split()) < 3:
            reasons.append("very_short_message")
            return out("clarify")
        return out("casual")

    if status == "experimental":  # keyword lexicon or unvalidated multilingual model
        reasons.append("experimental_signal")
        if label in NEGATIVE:
            return out("empathize", conf)
        if label in POSITIVE:
            return out("celebrate", conf)
        return out("casual", conf)

    if status == "uncertain" or (conf is not None and conf < min_confidence):
        reasons.append("low_confidence")
        if label in NEGATIVE:
            reasons.append("possible_negative_feeling")
            return out("clarify", conf)
        return out("casual", conf)

    if label in POSITIVE and conf >= GOOD:
        reasons.append("positive_emotion_detected")
        return out("celebrate", conf)
    if label in NEGATIVE:
        reasons.append("negative_emotion_detected")
        if distress and distress.get("level") == "elevated":
            reasons.append("sustained_negative_trend")
            return out("support", conf)
        if conf >= STRONG:
            reasons.append("high_confidence")
            return out("support", conf)
        return out("empathize", conf)
    reasons.append("neutral_or_mild_emotion")
    return out("casual", conf)
