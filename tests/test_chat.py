from conftest import register
from models import Message


def chat(c, text, **kw):
    return c.post("/api/chat", json={"message": text, **kw})


def test_chat_pipeline_and_storage(app, user):
    r = chat(user, "I feel so sad and lonely").get_json()
    assert r["analysis"]["emotion"] == "sadness" and r["analysis"]["emotion_confidence"] == 0.91
    assert r["decision"]["strategy"] in ("support", "empathize")
    assert r["assistant_message"]["source"] == "gemini"
    conv = r["conversation"]["id"]
    detail = user.get(f"/api/conversations/{conv}").get_json()
    assert len(detail["messages"]) == 2 and len(detail["observations"]) == 1
    assert detail["conversation"]["title"].startswith("I feel so sad")


def test_context_is_bounded(app, user):
    ai = app.extensions["aura"].ai
    conv = chat(user, "message 0").get_json()["conversation"]["id"]
    for i in range(1, 12):
        chat(user, f"message {i}", conversation_id=conv)
    assert len(ai.calls[-1]["history"]) <= app.config["CONTEXT_MESSAGES"]


def test_gemini_failure_is_labelled_fallback_and_retry_works(app, user):
    ai = app.extensions["aura"].ai
    ai.fail = True
    r = chat(user, "Hello there friend").get_json()
    assert r["assistant_message"]["source"] == "fallback" and r["retryable"] is True
    assert "temporarily unavailable" in r["assistant_message"]["content"]
    ai.fail = False
    r2 = user.post("/api/chat", json={"conversation_id": r["conversation"]["id"], "regenerate": True}).get_json()
    assert r2["assistant_message"]["source"] == "gemini"
    detail = user.get(f"/api/conversations/{r['conversation']['id']}").get_json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


def test_safety_message_is_template_when_ai_down(app, user):
    app.extensions["aura"].ai.fail = True
    r = chat(user, "I want to die").get_json()
    assert r["decision"]["strategy"] == "safety_support"
    assert r["assistant_message"]["source"] == "safety_template"


def test_validation(user):
    assert chat(user, "   ").status_code == 400
    assert chat(user, "x" * 5000).status_code == 400


def test_pin_rename_delete(user):
    conv = chat(user, "First chat").get_json()["conversation"]["id"]
    assert user.patch(f"/api/conversations/{conv}", json={"pinned": True}).get_json()["conversation"]["pinned"] is True
    assert user.patch(f"/api/conversations/{conv}", json={"title": "Renamed"}).get_json()["conversation"]["title"] == "Renamed"
    assert user.get("/api/conversations").get_json()["conversations"][0]["pinned"] is True
    assert user.delete(f"/api/conversations/{conv}").status_code == 200
    assert user.get(f"/api/conversations/{conv}").status_code == 404


def test_explicit_remember_and_deleting_chat_keeps_memory(app, user):
    r = chat(user, "Remember that I prefer short answers").get_json()
    assert r["memory_saved"] == "I prefer short answers"
    user.delete(f"/api/conversations/{r['conversation']['id']}")
    assert len(user.get("/api/memory").get_json()["items"]) == 1
    with app.app_context():
        assert Message.query.count() == 0


def test_memory_used_in_prompt_only_when_relevant(app, user):
    user.post("/api/memory", json={"content": "Studies computer science"})
    chat(user, "Help with my computer science homework")
    assert "Studies computer science" in app.extensions["aura"].ai.calls[-1]["prompt"]
    chat(user, "What is the capital of France?")
    assert "Studies computer science" not in app.extensions["aura"].ai.calls[-1]["prompt"]


def test_distress_needs_enough_observations(user):
    conv = None
    levels = []
    for _ in range(4):
        r = chat(user, "I feel sad and lonely", conversation_id=conv).get_json()
        conv = r["conversation"]["id"]
        levels.append(r["distress"]["level"])
    assert levels[0] == "insufficient_data" and levels[-1] in ("moderate", "elevated")
    assert "diagnos" not in r["distress"]["label"].lower() and "experimental" in r["distress"]["label"].lower()


def test_user_data_isolation(app):
    a, b = app.test_client(), app.test_client()
    register(a, "a@example.com", "Ayesha Khan")
    register(b, "b@example.com", "Bilal Ahmed")
    conv = chat(a, "private thought").get_json()["conversation"]["id"]
    a.post("/api/memory", json={"content": "secret fact"})
    assert b.get(f"/api/conversations/{conv}").status_code == 404
    assert b.delete(f"/api/conversations/{conv}").status_code == 404
    assert b.patch(f"/api/conversations/{conv}", json={"pinned": True}).status_code == 404
    assert chat(b, "hi", conversation_id=conv).status_code == 404
    assert b.get("/api/conversations").get_json()["conversations"] == []
    assert b.get("/api/memory").get_json()["items"] == []
    mem_id = a.get("/api/memory").get_json()["items"][0]["id"]
    assert b.delete(f"/api/memory/{mem_id}").status_code == 404


def test_no_unnecessary_empty_conversations(user):
    assert user.get("/api/conversations").get_json()["conversations"] == []
