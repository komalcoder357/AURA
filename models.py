
"""Database models. Conversations own their messages (cascade delete);
long-term memory records are independent of conversations on purpose."""
import datetime as dt
import json
import uuid

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def new_id():
    return uuid.uuid4().hex


def iso(value):
    return value.isoformat() + "Z" if value else None


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    avatar_blob = db.Column(db.LargeBinary)
    avatar_mime = db.Column(db.String(20))
    avatar_version = db.Column(db.Integer, default=0)

    prefs = db.relationship(
        "UserPreferences", uselist=False, backref="user",
        cascade="all, delete-orphan"
    )
    conversations = db.relationship(
        "Conversation", backref="user", cascade="all, delete-orphan"
    )
    memories = db.relationship(
        "MemoryRecord", backref="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def avatar_url(self):
        return f"/api/avatar?v={self.avatar_version or 0}" if self.avatar_blob else None

    @property
    def initials(self):
        parts = [p for p in self.display_name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()


class UserPreferences(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    theme = db.Column(db.String(20), default="baby-pink", nullable=False)
    memory_enabled = db.Column(db.Boolean, default=True, nullable=False)
    language = db.Column(db.String(10), default="auto", nullable=False)
    response_style = db.Column(db.String(10), default="balanced", nullable=False)
    voice_lang = db.Column(db.String(10), default="en-US", nullable=False)
    auto_speak = db.Column(db.Boolean, default=False, nullable=False)
    appearance = db.Column(db.String(10), default="light", nullable=False)
    custom_colors = db.Column(db.Text)
    reduce_motion = db.Column(db.Boolean, default=False, nullable=False)
    voice_responses = db.Column(db.Boolean, default=True, nullable=False)
    voice_name = db.Column(db.String(200), default="", nullable=False)
    voice_rate = db.Column(db.Float, default=1.0, nullable=False)
    voice_volume = db.Column(db.Float, default=1.0, nullable=False)
    voice_greeting = db.Column(db.Boolean, default=True, nullable=False)
    voice_auto_submit = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def colors(self):
        try:
            return json.loads(self.custom_colors) if self.custom_colors else None
        except (ValueError, TypeError):
            return None

    def to_dict(self):
        return {
            "theme": self.theme,
            "appearance": self.appearance,
            "custom_colors": self.colors,
            "reduce_motion": self.reduce_motion,
            "memory_enabled": self.memory_enabled,
            "language": self.language,
            "response_style": self.response_style,
            "voice_lang": self.voice_lang,
            "auto_speak": self.auto_speak,
            "voice_responses": self.voice_responses,
            "voice_name": self.voice_name,
            "voice_rate": self.voice_rate,
            "voice_volume": self.voice_volume,
            "voice_greeting": self.voice_greeting,
            "voice_auto_submit": self.voice_auto_submit,
        }


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), unique=True, default=new_id, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(120), default="New chat")
    pinned = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow)

    messages = db.relationship(
        "Message",
        backref="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )

    __table_args__ = (
        db.Index("ix_conversation_user_updated", "user_id", "updated_at"),
    )

    def summary(self):
        return {
            "id": self.public_id,
            "title": self.title,
            "pinned": self.pinned,
            "updated_at": iso(self.updated_at),
        }


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversation.id"), nullable=False, index=True
    )
    role = db.Column(db.String(10), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    source = db.Column(db.String(20))  # assistant only: gemini | fallback | safety_template
    input_source = db.Column(
        db.String(20), nullable=True
    )  # user only: typed | voice

    analysis_json = db.Column(db.Text)  # user only: emotion result + distress
    decision_json = db.Column(db.Text)  # user only: decision engine output

    latency_ms = db.Column(db.Integer)  # assistant only: total AI generation time
    ttft_ms = db.Column(db.Integer)  # assistant only: time to first streamed chunk
    error_type = db.Column(db.String(60))  # assistant only: provider error reason, if any
    latency_json = db.Column(db.Text)  # assistant only: measured timings in ms (no content)

    @property
    def analysis(self):
        return json.loads(self.analysis_json) if self.analysis_json else None

    @property
    def decision(self):
        return json.loads(self.decision_json) if self.decision_json else None

    def to_dict(self):
        out = {
            "role": self.role,
            "content": self.content,
            "created_at": iso(self.created_at),
        }

        if self.role == "assistant":
            out["source"] = self.source
        else:
            out["analysis"] = self.analysis
            out["decision"] = self.decision
            out["input_source"] = self.input_source

        return out


class MemoryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), unique=True, default=new_id)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    content = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.public_id,
            "content": self.content,
            "created_at": iso(self.created_at),
        }
