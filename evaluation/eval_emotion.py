"""Measures the CURRENT emotion pipeline on evaluation/dataset.csv. Prints only what it measured.
Run:  python evaluation/eval_emotion.py
The starter dataset is small and its labels were written by hand: extend it with your own, independently
labelled sentences before quoting any number. If the English model can't load, English is reported as 'not run'."""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config  # noqa: E402
from modules.emotion import EmotionAnalyzer  # noqa: E402
from modules.language import detect_language, normalize  # noqa: E402

an = EmotionAnalyzer(Config.EMOTION_MODEL_EN, Config.EMOTION_MODEL_MULTI, "lazy", Config.EMOTION_MIN_CONFIDENCE)
rows = list(csv.DictReader(open(os.path.join(os.path.dirname(__file__), "dataset.csv"), encoding="utf-8")))
stats = defaultdict(lambda: {"n": 0, "correct": 0, "abstained": 0, "unavailable": 0, "lang_ok": 0})
for r in rows:
    lang = detect_language(r["text"])
    res = an.analyze(normalize(r["text"], lang["code"]), lang)
    s = stats[r["language"]]
    s["n"] += 1
    s["lang_ok"] += lang["code"] == r["language"]
    if res["analysis_status"] in ("model_unavailable", "model_error"):
        s["unavailable"] += 1
    elif not res["emotion"] or res["analysis_status"] == "uncertain":
        s["abstained"] += 1
    elif res["emotion"] == r["expected"]:
        s["correct"] += 1
print(f"{'language':10} {'n':>3} {'lang-detect ok':>14} {'answered':>9} {'correct':>8} {'abstained':>10} {'not run':>8}")
for lang, s in stats.items():
    answered = s["n"] - s["abstained"] - s["unavailable"]
    acc = f"{s['correct']}/{answered}" if answered else "n/a"
    print(f"{lang:10} {s['n']:>3} {s['lang_ok']:>14} {answered:>9} {acc:>8} {s['abstained']:>10} {s['unavailable']:>8}")
print("\nSmall hand-labelled sample: indicative only, not an accuracy claim. Roman Urdu/Urdu use an experimental keyword list "
      "unless EMOTION_MODEL_MULTI is set. 'correct' counts only answered (non-abstained) rows.")
