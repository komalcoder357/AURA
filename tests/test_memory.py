from models import MemoryRecord, User
from modules import memory as mem


def test_extract_explicit_memory():
    assert mem.extract_explicit_memory("Remember that I prefer short answers") == "I prefer short answers"
    assert mem.extract_explicit_memory("yaad rakho ke mera exam kal hai") == "mera exam kal hai"
    assert mem.extract_explicit_memory("I remember my exam") is None


def test_memory_api_crud_and_toggle(user):
    assert user.post("/api/memory", json={"content": "Prefers Roman Urdu replies"}).status_code == 201
    items = user.get("/api/memory").get_json()["items"]
    assert len(items) == 1
    assert user.delete(f"/api/memory/{items[0]['id']}").status_code == 200
    user.post("/api/memory", json={"content": "Likes tea"})
    assert user.delete("/api/memory").status_code == 200
    assert user.get("/api/memory").get_json()["items"] == []


def test_retrieval_is_relevant_only_and_respects_toggle(app, user):
    user.post("/api/memory", json={"content": "Studies computer science in Lahore"})
    user.post("/api/memory", json={"content": "Favourite food is biryani"})
    with app.app_context():
        u = User.query.first()
        got = mem.retrieve(u, "help me with my computer science project", 4)
        assert [r.content for r in got] == ["Studies computer science in Lahore"]
    user.patch("/api/settings", json={"memory_enabled": False})
    with app.app_context():
        assert mem.retrieve(User.query.first(), "computer science", 4) == []
