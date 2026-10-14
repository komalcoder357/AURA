import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app  # noqa: E402
from modules.ai_service import AIUnavailable  # noqa: E402
from modules.emotion import EmotionAnalyzer  # noqa: E402


def fake_factory(model_name):
    def pipe(text, **kwargs):
        t = text.lower()
        if "sad" in t or "lonely" in t:
            return [[{"label": "sadness", "score": 0.91}, {"label": "joy", "score": 0.09}]]
        if "great" in t or "happy" in t:
            return [[{"label": "joy", "score": 0.88}, {"label": "neutral", "score": 0.12}]]
        return [[{"label": "neutral", "score": 0.4}, {"label": "joy", "score": 0.35}, {"label": "sadness", "score": 0.25}]]
    return pipe


class FakeAI:
    def __init__(self):
        self.fail = False
        self.explode = False  # raise a non-AIUnavailable exception to prove the app never crashes
        self.calls = []

    def generate(self, message, history, system_prompt, attempts=2):
        self.calls.append({"message": message, "history": history, "prompt": system_prompt})
        if self.explode:
            raise RuntimeError("boom")
        if self.fail:
            raise AIUnavailable("test_failure")
        return "Fake reply to: " + message

    def stream(self, message, history, system_prompt, attempts=2):
        self.calls.append({"message": message, "history": history, "prompt": system_prompt})
        if self.explode:
            raise RuntimeError("boom")
        if self.fail:
            raise AIUnavailable("test_failure")
        words = ("Fake reply to: " + message).split(" ")
        for i, w in enumerate(words):
            if getattr(self, "fail_after", None) is not None and i >= self.fail_after:
                raise AIUnavailable("mid_stream")
            yield w + (" " if i < len(words) - 1 else "")


@pytest.fixture()
def app():
    from routes import auth as auth_routes
    auth_routes._failures.clear()  # the login throttle is module-level state; isolate tests from each other
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False,
                      "EMOTION_LOAD": "lazy", "SECRET_KEY": "test"})
    svc = app.extensions["aura"]
    svc.emotion = EmotionAnalyzer("en-model", "", "lazy", 0.5, factory=fake_factory)
    svc.ai = FakeAI()
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="a@example.com", name="Ayesha Khan", password="password123"):
    return client.post("/register", data={"email": email, "display_name": name, "password": password,
                                          "confirm_password": password}, follow_redirects=False)


@pytest.fixture()
def user(client):
    register(client)
    return client
