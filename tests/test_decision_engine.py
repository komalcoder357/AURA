from modules.decision_engine import decide

SAFE = {"flag": False}


def emo(label, conf, status="success", method="hf_english"):
    return {"emotion": label, "emotion_confidence": conf, "analysis_status": status, "analysis_method": method}


def test_safety_overrides_everything():
    d = decide("I want to die", emo("joy", 0.99), {"flag": True})
    assert d["strategy"] == "safety_support" and d["reason_codes"] == ["safety_language_detected"]


def test_task_ignores_negative_emotion():
    d = decide("How do I fix this Python error?", emo("sadness", 0.95), SAFE)
    assert d["strategy"] == "neutral" and "task_request" in d["reason_codes"]


def test_feeling_question_is_not_a_task():
    d = decide("Why am I so sad lately", emo("sadness", 0.9), SAFE)
    assert d["strategy"] == "support"


def test_positive_celebrates():
    assert decide("I got the job!", emo("joy", 0.9), SAFE)["strategy"] == "celebrate"


def test_moderate_negative_empathizes():
    assert decide("Work was rough", emo("sadness", 0.7), SAFE)["strategy"] == "empathize"


def test_low_confidence_negative_clarifies_not_assumes():
    d = decide("Things are weird", emo("sadness", 0.4, "uncertain"), SAFE)
    assert d["strategy"] == "clarify" and "low_confidence" in d["reason_codes"]


def test_unavailable_model_falls_back_to_casual():
    d = decide("Just chilling at home tonight", {"emotion": None, "analysis_status": "model_unavailable"}, SAFE)
    assert d["strategy"] == "casual" and "no_reliable_emotion_signal" in d["reason_codes"]


def test_sustained_negative_trend_escalates_to_support():
    d = decide("Another bad day", emo("sadness", 0.7), SAFE, {"level": "elevated"})
    assert d["strategy"] == "support" and "sustained_negative_trend" in d["reason_codes"]


def test_experimental_signal_never_escalates():
    d = decide("Main udaas hun", emo("sadness", None, "experimental", "lexicon_experimental"), SAFE, {"level": "elevated"})
    assert d["strategy"] == "empathize" and "experimental_signal" in d["reason_codes"]
