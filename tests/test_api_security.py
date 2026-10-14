import pytest

from app import create_app


def test_security_headers(user):
    r = user.get("/")
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in user.get("/api/conversations").headers["Cache-Control"]


def test_no_inline_scripts_or_styles_in_index(user):
    html = user.get("/").get_data(as_text=True)
    assert "<script>" not in html and ' style="' not in html and "onclick=" not in html


def test_csrf_enforced_when_enabled():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "EMOTION_LOAD": "off", "SECRET_KEY": "t"})
    app.config["WTF_CSRF_ENABLED"] = True
    c = app.test_client()
    assert c.post("/register", data={"email": "x@y.com", "display_name": "X", "password": "password123",
                                     "confirm_password": "password123"}).status_code == 400
    assert c.post("/api/chat", json={"message": "hi"}).status_code in (400, 401)


def test_password_not_stored_plain(app, user):
    from models import User
    with app.app_context():
        assert "password123" not in User.query.first().password_hash


def test_html_in_message_is_returned_as_data_not_markup(user):
    r = user.post("/api/chat", json={"message": "<img src=x onerror=alert(1)>"}).get_json()
    assert r["user_message"]["content"] == "<img src=x onerror=alert(1)>"  # frontend renders with textContent
