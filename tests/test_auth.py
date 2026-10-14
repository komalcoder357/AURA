from conftest import register


def test_register_login_logout(client):
    assert register(client).status_code == 302
    assert client.get("/").status_code == 200
    assert client.post("/logout").status_code == 302
    assert "Log in" in client.get("/").get_data(as_text=True)  # anonymous users see the landing page
    r = client.post("/login", data={"email": "a@example.com", "password": "password123"})
    assert r.status_code == 302


def test_wrong_password_and_duplicate(client):
    register(client)
    client.post("/logout")
    assert client.post("/login", data={"email": "a@example.com", "password": "nope"}).status_code == 401
    assert register(client).status_code == 400


def test_short_password_rejected(client):
    assert register(client, password="short").status_code == 400


def test_login_throttle(client):
    register(client)
    client.post("/logout")
    codes = [client.post("/login", data={"email": "a@example.com", "password": "bad"}).status_code for _ in range(7)]
    assert 429 in codes


def test_initials_from_display_name(app, user):
    r = user.get("/api/settings").get_json()
    assert r["profile"]["initials"] == "AK"


def test_api_requires_login(client):
    assert client.get("/api/conversations").status_code == 401
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401
    assert client.get("/api/memory").status_code == 401
