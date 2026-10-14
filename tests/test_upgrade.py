import io
import json
import sqlite3

import pytest

from app import create_app
from conftest import register
from modules.safety import check_safety
from modules.theme import contrast, validate_custom

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def chat(c, text, **kw):
    return c.post("/api/chat", json={"message": text, **kw})


def stream(c, payload):
    r = c.post("/api/chat/stream", json=payload)
    return [json.loads(line) for line in r.get_data(as_text=True).splitlines() if line.strip()]


# ---------- search ----------
def test_search_titles_and_messages_case_insensitive_user_scoped(app):
    a, b = app.test_client(), app.test_client()
    register(a, "a@example.com", "Ayesha Khan"); register(b, "b@example.com", "Bilal Ahmed")
    chat(a, "Planning a Birthday party for my sister")
    chat(a, "Something else entirely, but I mention BIRTHDAY cake here too")
    chat(b, "my own birthday secret")
    r = a.get("/api/search?q=birthday").get_json()["results"]
    assert len(r) == 2 and {x["match"] for x in r} <= {"title", "message"}
    assert all("secret" not in x["snippet"] for x in r)
    assert b.get("/api/search?q=birthday").get_json()["results"][0]["snippet"].startswith("my own")
    assert a.get("/api/search?q=").get_json()["results"] == []


def test_search_escapes_wildcards_and_never_calls_ai(app, user):
    chat(user, "hello world")
    calls = len(app.extensions["aura"].ai.calls)
    assert user.get("/api/search?q=%25").get_json()["results"] == []
    assert user.get("/api/search?q=_").get_json()["results"] == []
    assert len(app.extensions["aura"].ai.calls) == calls


def test_search_requires_login(client):
    assert client.get("/api/search?q=x").status_code == 401


# ---------- unicode / rtl ----------
def test_urdu_text_round_trips(user):
    text = "مجھے آج بہت اداسی ہو رہی ہے, mood off hai"
    r = chat(user, text).get_json()
    cid = r["conversation"]["id"]
    assert user.get(f"/api/conversations/{cid}").get_json()["messages"][0]["content"] == text
    assert user.get("/api/search?q=اداسی").get_json()["results"]


# ---------- profile ----------
def test_profile_name_update_and_validation(user):
    assert user.patch("/api/profile", json={"display_name": "  Komal   Rafique "}).get_json()["initials"] == "KR"
    assert user.get("/api/settings").get_json()["profile"]["display_name"] == "Komal Rafique"
    assert user.patch("/api/profile", json={"display_name": "   "}).status_code == 400
    assert user.patch("/api/profile", json={"display_name": "x" * 61}).status_code == 400


def test_avatar_upload_is_content_checked_and_private(app):
    a, b = app.test_client(), app.test_client()
    register(a, "a@example.com", "Ayesha Khan"); register(b, "b@example.com", "Bilal Ahmed")
    assert a.post("/api/profile/avatar", data={"avatar": (io.BytesIO(b"<script>alert(1)</script>"), "x.png")},
                  content_type="multipart/form-data").status_code == 400  # fake png rejected by content
    assert a.post("/api/profile/avatar", data={"avatar": (io.BytesIO(PNG), "me.png")}, content_type="multipart/form-data").status_code == 200
    assert a.get("/api/avatar").mimetype == "image/png"
    assert b.get("/api/avatar").status_code == 404                   # other users never see it
    assert a.get("/api/settings").get_json()["profile"]["avatar_url"].startswith("/api/avatar")
    big = io.BytesIO(PNG + b"0" * 400_000)
    assert a.post("/api/profile/avatar", data={"avatar": (big, "big.png")}, content_type="multipart/form-data").status_code == 400
    assert a.delete("/api/profile/avatar").status_code == 200 and a.get("/api/avatar").status_code == 404


def test_email_cannot_be_changed_via_profile(user):
    user.patch("/api/profile", json={"display_name": "New Name", "email": "evil@example.com"})
    assert user.get("/api/settings").get_json()["profile"]["email"] == "a@example.com"


# ---------- themes ----------
def test_theme_mode_motion_voice_prefs_persist_across_logout(app):
    c = app.test_client(); register(c)
    c.patch("/api/settings", json={"theme": "lavender", "appearance": "dark", "reduce_motion": True, "voice_rate": 1.3,
                                   "voice_name": "Zira", "voice_auto_submit": False})
    c.post("/logout")
    c.post("/login", data={"email": "a@example.com", "password": "password123"})
    s = c.get("/api/settings").get_json()["settings"]
    assert (s["theme"], s["appearance"], s["reduce_motion"], s["voice_rate"], s["voice_name"], s["voice_auto_submit"]) == \
        ("lavender", "dark", True, 1.3, "Zira", False)
    html = c.get("/").get_data(as_text=True)
    assert 'data-theme="lavender"' in html and 'data-mode="dark"' in html and 'data-motion="reduced"' in html


def test_settings_validation_ranges(user):
    assert user.patch("/api/settings", json={"voice_rate": 9}).status_code == 400
    assert user.patch("/api/settings", json={"voice_volume": -1}).status_code == 400
    assert user.patch("/api/settings", json={"appearance": "blue"}).status_code == 400


def test_custom_colors_validated_persisted_and_served_per_user(app):
    a, b = app.test_client(), app.test_client()
    register(a, "a@example.com", "A A"); register(b, "b@example.com", "B B")
    good = {"bg": "#fff5f8", "accent": "#b8426d", "card": "#ffffff", "text": "#222222"}
    assert a.patch("/api/settings", json={"custom_colors": good}).status_code == 200
    assert "#b8426d" in a.get("/theme.css").get_data(as_text=True)
    assert "#b8426d" not in b.get("/theme.css").get_data(as_text=True)         # preferences are per account
    assert 'data-custom="1"' in a.get("/").get_data(as_text=True)
    assert a.patch("/api/settings", json={"custom_colors": {**good, "text": "#ffeeee"}}).status_code == 400  # low contrast
    assert a.patch("/api/settings", json={"custom_colors": {**good, "bg": "red"}}).status_code == 400          # not HEX
    assert a.patch("/api/settings", json={"custom_colors": {"bg": "#ffffff"}}).status_code == 400
    assert a.patch("/api/settings", json={"custom_colors": None}).status_code == 200                           # reset
    assert "no custom" in a.get("/theme.css").get_data(as_text=True)


def test_contrast_math():
    assert round(contrast("#000000", "#ffffff")) == 21
    assert validate_custom({"bg": "#ffffff", "accent": "#ff0000", "card": "#ffffff", "text": "#000000"})[1] is None


# ---------- auth ----------
def test_login_error_is_generic_for_unknown_email_and_wrong_password(app):
    c = app.test_client(); register(c); c.post("/logout")
    j = {"Accept": "application/json"}
    r1 = c.post("/login", json={"email": "a@example.com", "password": "wrongpass1"}, headers=j)
    r2 = c.post("/login", json={"email": "nobody@example.com", "password": "wrongpass1"}, headers=j)
    assert r1.status_code == r2.status_code == 401 and r1.get_json()["error"] == r2.get_json()["error"]
    assert "Unable to sign in with those details" in r1.get_json()["error"]


def test_login_json_success_and_html_preserves_email_not_password(app):
    c = app.test_client(); register(c); c.post("/logout")
    assert c.post("/login", json={"email": "a@example.com", "password": "password123"}).get_json()["ok"] is True
    c.post("/logout")
    html = c.post("/login", data={"email": "a@example.com", "password": "secretwrong1"}).get_data(as_text=True)
    assert 'value="a@example.com"' in html and "secretwrong1" not in html


def test_register_rules_and_confirm_and_no_enumeration(app):
    c = app.test_client()
    bad = c.post("/register", json={"display_name": "X", "email": "x@y.com", "password": "abcdefgh", "confirm_password": "abcdefgh"})
    assert bad.status_code == 400 and "password" in bad.get_json()["field_errors"]   # needs a digit
    mism = c.post("/register", json={"display_name": "X", "email": "x@y.com", "password": "abcdefg1", "confirm_password": "abcdefg2"})
    assert "confirm_password" in mism.get_json()["field_errors"]
    ok = c.post("/register", json={"display_name": "X", "email": "x@y.com", "password": "abcdefg1", "confirm_password": "abcdefg1"})
    assert ok.get_json()["ok"] is True
    c.post("/logout")
    dup = c.post("/register", json={"display_name": "X", "email": "x@y.com", "password": "abcdefg1", "confirm_password": "abcdefg1"})
    assert dup.status_code == 400 and "already" not in dup.get_json()["error"].lower()


def test_auth_pages_have_working_eye_toggle_markup(client):
    html = client.get("/register").get_data(as_text=True)
    assert html.count("data-pw-toggle") == 2 and 'type="password"' in html and "confirm_password" in html
    assert client.get("/login").get_data(as_text=True).count("data-pw-toggle") == 1


# ---------- streaming ----------
def test_stream_protocol_and_storage(app, user):
    lines = stream(user, {"message": "I feel so sad and lonely"})
    assert lines[0]["type"] == "meta" and lines[-1]["type"] == "done"
    deltas = [l["text"] for l in lines if l["type"] == "delta"]
    assert len(deltas) > 1 and "".join(deltas) == lines[-1]["assistant_message"]["content"]
    assert lines[0]["analysis"]["emotion"] == "sadness"
    assert lines[-1]["timings_ms"]["first_chunk"] is not None
    cid = lines[0]["conversation"]["id"]
    assert len(user.get(f"/api/conversations/{cid}").get_json()["messages"]) == 2


def test_stream_failure_before_first_chunk_is_labelled_fallback_and_retry_works(app, user):
    ai = app.extensions["aura"].ai
    ai.fail = True
    lines = stream(user, {"message": "Hello there friend"})
    assert lines[-1]["assistant_message"]["source"] == "fallback" and lines[-1]["retryable"] is True
    ai.fail = False
    cid = lines[0]["conversation"]["id"]
    again = stream(user, {"conversation_id": cid, "regenerate": True})
    assert again[-1]["assistant_message"]["source"] == "gemini"
    assert [m["role"] for m in user.get(f"/api/conversations/{cid}").get_json()["messages"]] == ["user", "assistant"]


def test_stream_failure_mid_stream_keeps_partial_and_label(app, user):
    app.extensions["aura"].ai.fail_after = 2
    lines = stream(user, {"message": "one two three four five"})
    done = lines[-1]
    assert done["assistant_message"]["source"] == "partial" and done["retryable"] is True and done["error_type"] == "mid_stream"
    assert done["assistant_message"]["content"].strip()


def test_stream_validation_and_ownership(app):
    a, b = app.test_client(), app.test_client()
    register(a, "a@example.com", "A A"); register(b, "b@example.com", "B B")
    cid = chat(a, "private").get_json()["conversation"]["id"]
    assert b.post("/api/chat/stream", json={"message": "hi", "conversation_id": cid}).status_code == 404
    assert a.post("/api/chat/stream", json={"message": "  "}).status_code == 400
    assert a.post("/api/chat/stream", json={"conversation_id": cid, "regenerate": True}).status_code == 400  # nothing to retry


def test_timings_stored_for_analytics(app, user):
    stream(user, {"message": "tell me about the weather today"})
    an = user.get("/api/analytics?days=7").get_json()
    assert an["user_messages"] == 1 and an["reply_sources"] == {"gemini": 1} and an["latency_ms"]["count"] == 1
    assert an["provider_errors"] == {}


# ---------- analytics ----------
def test_analytics_isolated_empty_and_counts_errors(app):
    a, b = app.test_client(), app.test_client()
    register(a, "a@example.com", "A A"); register(b, "b@example.com", "B B")
    app.extensions["aura"].ai.fail = True
    chat(a, "I am sad and lonely")
    an = a.get("/api/analytics?days=30").get_json()
    assert an["provider_errors"] == {"test_failure": 1} and an["reply_sources"] == {"fallback": 1}
    assert "I am sad" not in json.dumps(an)                          # no message content in analytics
    assert b.get("/api/analytics").get_json()["user_messages"] == 0
    assert a.get("/api/analytics?days=abc").status_code == 200


# ---------- safety ----------
@pytest.mark.parametrize("text", [
    "I want to kill myself", "I'm planning to end my life tonight", "I don't want to live anymore",
    "khudkushi karna chahta hun", "main apni jaan le lun ga", "میں خودکشی کرنا چاہتا ہوں", "I keep thinking about suicide"])
def test_safety_high_risk_detected(text):
    r = check_safety(text)
    assert r["flag"] is True and r["level"] == "high"


@pytest.mark.parametrize("text", [
    "everyone would be better off without me", "I can't go on like this", "I wish I wouldn't wake up",
    "main bojh hun sab pe", "زندگی سے تھک گیا ہوں"])
def test_safety_indirect_language_is_possible_not_high(text):
    r = check_safety(text)
    assert r["flag"] is False and r["level"] == "possible"


@pytest.mark.parametrize("text", [
    "I'm so sad today", "work is killing me", "I'm going to kill this bug before lunch", "I'm dying to see that movie",
    "I'm dead tired", "my exam went badly and I'm frustrated", "mujhe bohat udaasi ho rahi hai"])
def test_safety_ordinary_negative_or_idioms_not_flagged(text):
    assert check_safety(text) == {"flag": False, "level": None, "category": None}


def test_indirect_risk_gets_gentle_checkin_not_template(app, user):
    r = chat(user, "everyone would be better off without me").get_json()
    assert "indirect_risk_language" in r["decision"]["reason_codes"]
    assert r["assistant_message"]["source"] == "gemini"
    assert "thinking about harming themselves" in app.extensions["aura"].ai.calls[-1]["prompt"]


def test_high_risk_uses_safety_strategy(user):
    assert chat(user, "I want to kill myself").get_json()["decision"]["strategy"] == "safety_support"


# ---------- landing / headers / migration ----------
def test_landing_page_and_csp(client):
    html = client.get("/").get_data(as_text=True)
    assert "Log in" in html and "Create account" in html
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "fonts.googleapis.com" in csp and "script-src 'self'" in csp and "unsafe-inline" not in csp
    assert "camera=(self)" in client.get("/").headers["Permissions-Policy"]


def test_index_has_webcam_disclaimer_exact_and_camera_not_autostarted(user):
    html = user.get("/").get_data(as_text=True)
    exact = ("Educational and research purposes only. This feature estimates visible facial-expression patterns and is not a "
             "medical diagnostic tool. It does not provide medical treatment, and facial expressions alone cannot reliably "
             "establish anxiety level or mental state.")
    assert exact in html
    assert "getUserMedia" not in html and "<video" in html


def test_migration_adds_columns_keeps_data_and_makes_backup(tmp_path):
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE user (id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL, display_name VARCHAR(80) NOT NULL,
        password_hash VARCHAR(255) NOT NULL, created_at DATETIME);
    CREATE TABLE user_preferences (user_id INTEGER PRIMARY KEY, theme VARCHAR(20) NOT NULL DEFAULT 'baby-pink',
        memory_enabled BOOLEAN NOT NULL DEFAULT 1, language VARCHAR(10) NOT NULL DEFAULT 'auto',
        response_style VARCHAR(10) NOT NULL DEFAULT 'balanced', voice_lang VARCHAR(10) NOT NULL DEFAULT 'en-US',
        auto_speak BOOLEAN NOT NULL DEFAULT 0);
    CREATE TABLE conversation (id INTEGER PRIMARY KEY, public_id VARCHAR(32), user_id INTEGER NOT NULL, title VARCHAR(120),
        pinned BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME, updated_at DATETIME);
    CREATE TABLE message (id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL, role VARCHAR(10) NOT NULL,
        content TEXT NOT NULL, created_at DATETIME, source VARCHAR(20), analysis_json TEXT, decision_json TEXT);
    INSERT INTO user VALUES (1, 'old@example.com', 'Old User', 'pbkdf2:sha256:hash', '2026-01-01 00:00:00');
    INSERT INTO user_preferences (user_id, theme) VALUES (1, 'classic');
    INSERT INTO conversation VALUES (1, 'abc123', 1, 'Old chat', 1, '2026-01-01', '2026-01-02');
    INSERT INTO message (id, conversation_id, role, content) VALUES (1, 1, 'user', 'میرا پرانا پیغام');
    """)
    con.commit(); con.close()
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db}", "WTF_CSRF_ENABLED": False,
                      "EMOTION_LOAD": "off", "SECRET_KEY": "t"})
    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(user_preferences)")}
    assert {"appearance", "custom_colors", "voice_rate", "reduce_motion", "voice_auto_submit"} <= cols
    assert con.execute("SELECT email, password_hash FROM user").fetchone() == ("old@example.com", "pbkdf2:sha256:hash")
    assert con.execute("SELECT content FROM message").fetchone()[0] == "میرا پرانا پیغام"
    assert con.execute("SELECT theme, appearance, voice_rate FROM user_preferences").fetchone() == ("neutral", "light", 1.0)
    backups = list((tmp_path / "backups").glob("aura-*.db"))
    assert len(backups) == 1                                          # a copy was made BEFORE the schema changed
    b = sqlite3.connect(backups[0])
    assert "appearance" not in {r[1] for r in b.execute("PRAGMA table_info(user_preferences)")}  # backup is the old schema
    assert b.execute("SELECT content FROM message").fetchone()[0] == "میرا پرانا پیغام"
    b.close()
    con.close()
    with app.app_context():
        from models import Conversation, User
        assert User.query.one().prefs.voice_name == "" and Conversation.query.one().title == "Old chat"


# ---------- provider robustness ----------
def test_real_ai_service_without_key_reports_missing_key_for_both_paths():
    from modules.ai_service import AIService, AIUnavailable
    svc = AIService("", "model")
    with pytest.raises(AIUnavailable, match="missing_api_key"):
        svc.generate("hi", [], "prompt")
    with pytest.raises(AIUnavailable, match="missing_api_key"):
        list(svc.stream("hi", [], "prompt"))


def test_unexpected_provider_exception_never_crashes_chat_or_stream(app, user):
    app.extensions["aura"].ai.explode = True
    r = chat(user, "Hello there friend").get_json()
    assert r["assistant_message"]["source"] == "fallback" and r["error_type"] == "RuntimeError"
    lines = stream(user, {"message": "Hello again friend"})
    assert lines[-1]["type"] == "done" and lines[-1]["assistant_message"]["source"] == "fallback"
