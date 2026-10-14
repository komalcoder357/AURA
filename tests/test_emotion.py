from conftest import fake_factory
from modules.emotion import EmotionAnalyzer
from modules.language import detect_language, normalize


def analyzer(factory=fake_factory, multi=""):
    return EmotionAnalyzer("en-model", multi, "lazy", 0.5, factory=factory)


def test_language_detection():
    assert detect_language("I feel really sad today")["code"] == "en"
    assert detect_language("Mujhe aj bohat udaasi ho rahi hai.")["code"] == "roman_ur"
    assert detect_language("مجھے بہت اداسی ہو رہی ہے")["code"] == "ur"
    assert detect_language("12345 !!!")["code"] == "unknown"


def test_normalize_keeps_meaning():
    assert normalize("Bohooooot  KHUSH", "roman_ur") == "bohoot khush"


def test_english_success_uses_model_output():
    lang = detect_language("I am so sad")
    r = analyzer().analyze("I am so sad", lang)
    assert r["emotion"] == "sadness" and r["emotion_confidence"] == 0.91
    assert r["analysis_status"] == "success" and r["emotion_intensity"] is None


def test_low_confidence_is_uncertain():
    r = analyzer().analyze("hello there", detect_language("hello there"))
    assert r["analysis_status"] == "uncertain"


def test_model_failure_is_explicit_not_faked():
    def broken(name):
        raise RuntimeError("download failed")
    r = analyzer(broken).analyze("I am sad", detect_language("I am sad"))
    assert r["analysis_status"] == "model_unavailable" and r["emotion"] is None


def test_roman_urdu_uses_experimental_lexicon():
    text = "Main bohat khush hun"
    r = analyzer().analyze(text, detect_language(text))
    assert r["emotion"] == "joy" and r["analysis_status"] == "experimental"
    assert r["emotion_confidence"] is None and r["analysis_method"] == "lexicon_experimental"


def test_urdu_script_lexicon():
    text = "مجھے بہت اداسی ہو رہی ہے"
    r = analyzer().analyze(text, detect_language(text))
    assert r["emotion"] == "sadness"


def test_negation_is_not_guessed():
    text = "Main khush nahi hun"
    r = analyzer().analyze(text, detect_language(text))
    assert r["emotion"] is None and r["analysis_status"] == "no_signal"


def test_urdu_without_signal_never_invents_label():
    text = "Aaj mausam kaisa hai"
    r = analyzer().analyze(text, detect_language(text))
    assert r["emotion"] is None


def test_insufficient_text():
    r = analyzer().analyze("a", detect_language("a"))
    assert r["analysis_status"] == "insufficient_text"
