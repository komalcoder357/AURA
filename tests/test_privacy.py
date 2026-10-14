from conftest import register


def test_settings_validation_and_persistence(user):
    assert user.patch("/api/settings", json={"theme": "lavender"}).status_code == 200
    assert user.get("/api/settings").get_json()["settings"]["theme"] == "lavender"
    assert user.patch("/api/settings", json={"theme": "neon-red"}).status_code == 400
    assert user.patch("/api/settings", json={"memory_enabled": "yes"}).status_code == 400


def test_delete_all_chats_keeps_memory(user):
    user.post("/api/chat", json={"message": "hello there"})
    user.post("/api/memory", json={"content": "keep me"})
    user.delete("/api/conversations")
    assert user.get("/api/conversations").get_json()["conversations"] == []
    assert len(user.get("/api/memory").get_json()["items"]) == 1


def test_privacy_page_states_limits(client):
    html = client.get("/privacy").get_data(as_text=True)
    assert "not a diagnosis" in html and "not emotional intensity" in html
