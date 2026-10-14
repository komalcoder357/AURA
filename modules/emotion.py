"""Emotion analysis. English uses a Hugging Face classifier. Urdu / Roman Urdu use a configured
multilingual model if (and only if) one is set; otherwise a small, clearly experimental keyword
lexicon is used. Nothing is ever invented: unsupported input returns emotion=None.

Scores from the HF models are raw softmax outputs, NOT calibrated probabilities."""
import threading
import time

from modules.language import tokens

NEGATIVE = {"sadness", "fear", "anger", "disgust"}
POSITIVE = {"joy", "love", "optimism", "trust"}

NEGATORS = {"nahi", "nahin", "na", "mat", "نہیں", "نا"}
LEXICON = {
    "joy": {"khush", "khushi", "kamyab", "kamyabi", "mubarak", "shandar", "zabardast", "maza", "mazay",
            "خوش", "خوشی", "کامیاب", "مبارک", "شاندار", "زبردست"},
    "sadness": {"udaas", "udaasi", "dukhi", "dukh", "rona", "royi", "tanha", "akela", "akeli",
                "اداس", "اداسی", "دکھ", "دکھی", "رونا", "تنہا", "اکیلا", "اکیلی"},
    "anger": {"gussa", "ghussa", "ghusse", "naraz", "غصہ", "غصے", "ناراض"},
    "fear": {"dar", "darr", "dara", "dari", "ghabrahat", "ghabra", "khauf", "pareshan", "pareshani",
             "ڈر", "گھبراہٹ", "پریشان", "پریشانی", "خوف"},
}


def _default_factory(model_name):
    from transformers import pipeline  # imported lazily: heavy dependency

    return pipeline("text-classification", model=model_name, top_k=None)


class EmotionAnalyzer:
    def __init__(self, en_model, multi_model="", load_mode="startup", min_confidence=0.5, factory=None):
        self.en_model = en_model
        self.multi_model = multi_model
        self.load_mode = load_mode
        self.min_confidence = min_confidence
        self._factory = factory or _default_factory
        self._pipes = {}
        self._errors = {}
        self._lock = threading.Lock()

    @classmethod
    def from_config(cls, cfg):
        return cls(cfg["EMOTION_MODEL_EN"], cfg["EMOTION_MODEL_MULTI"], cfg["EMOTION_LOAD"], cfg["EMOTION_MIN_CONFIDENCE"])

    def warmup(self):
        if self.load_mode != "off":
            self._get_pipe(self.en_model)

    def _get_pipe(self, name):
        if self.load_mode == "off" or not name:
            return None
        with self._lock:
            if name in self._pipes:
                return self._pipes[name]
            if name in self._errors:
                return None
            try:
                self._pipes[name] = self._factory(name)
            except Exception as exc:  # download / import failure -> explicit unavailable status
                self._errors[name] = type(exc).__name__
                return None
            return self._pipes[name]

    @staticmethod
    def _base(code):
        return {"language": code, "emotion": None, "emotion_confidence": None, "emotion_intensity": None,
                "scores": {}, "analysis_status": "unavailable", "analysis_method": None, "model_version": None,
                "latency_ms": 0}

    def analyze(self, text, language):
        start = time.perf_counter()
        code = language["code"]
        out = self._base(code)
        if len(text.strip()) < 2 or code == "unknown":
            out["analysis_status"] = "insufficient_text"
        elif code == "en":
            self._hf(out, text, self.en_model, "hf_english")
        elif self.multi_model:
            self._hf(out, text, self.multi_model, "hf_multilingual")
            if out["analysis_status"] == "success":
                out["analysis_status"] = "experimental"  # not validated on Urdu / Roman Urdu by us
        else:
            self._lexicon(out, text)
        out["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        return out

    def _hf(self, out, text, model_name, method):
        out["analysis_method"], out["model_version"] = method, model_name
        pipe = self._get_pipe(model_name)
        if pipe is None:
            out["analysis_status"] = "model_unavailable"
            return
        try:
            raw = pipe(text, truncation=True, max_length=256)
        except Exception:
            out["analysis_status"] = "model_error"
            return
        if raw and isinstance(raw[0], list):
            raw = raw[0]
        scores = {str(item["label"]).lower(): float(item["score"]) for item in raw}
        if not scores:
            out["analysis_status"] = "model_error"
            return
        label = max(scores, key=scores.get)
        out.update(emotion=label, emotion_confidence=round(scores[label], 4),
                   scores={k: round(v, 4) for k, v in scores.items()})
        out["analysis_status"] = "success" if scores[label] >= self.min_confidence else "uncertain"

    def _lexicon(self, out, text):
        out["analysis_method"], out["model_version"] = "lexicon_experimental", "keyword-lexicon-v1"
        words = tokens(text)
        counts = {}
        for i, word in enumerate(words):
            for emotion, vocab in LEXICON.items():
                if word in vocab:
                    window = words[max(0, i - 2): i + 3]
                    if any(w in NEGATORS for w in window):
                        continue  # negation nearby: do not guess
                    counts[emotion] = counts.get(emotion, 0) + 1
        if not counts:
            out["analysis_status"] = "no_signal"
            return
        total = sum(counts.values())
        out["scores"] = {k: round(v / total, 3) for k, v in counts.items()}
        out["emotion"] = max(counts, key=counts.get)
        out["analysis_status"] = "experimental"  # keyword share, so confidence stays None
