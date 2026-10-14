"""EXPERIMENTAL distress-related signal: the share of negative emotion labels among the most recent
usable observations. A documented heuristic, not a diagnosis or a validated assessment."""
from modules.emotion import NEGATIVE

LABEL = "Distress-related signals (experimental)"


def usable(obs):
    if not obs or not obs.get("emotion"):
        return False
    if obs.get("analysis_method") == "lexicon_experimental":
        return True
    return obs.get("analysis_status") == "success"


def distress_signal(observations, window=5, min_observations=3):
    recent = [o for o in observations if usable(o)][-window:]
    result = {"label": LABEL, "level": "insufficient_data", "observations": len(recent), "window": window,
              "basis": "share of negative emotion labels in recent messages"}
    if len(recent) < min_observations:
        return result
    share = sum(1 for o in recent if o["emotion"] in NEGATIVE) / len(recent)
    result["negative_share"] = round(share, 2)
    result["level"] = "elevated" if share >= 0.8 and len(recent) >= 4 else "moderate" if share >= 0.5 else "low"
    return result
