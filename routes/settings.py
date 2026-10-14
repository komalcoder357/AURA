import json

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from config import THEMES
from extensions import db
from models import iso
from modules.theme import validate_custom

bp = Blueprint("settings", __name__, url_prefix="/api")
CHOICES = {
    "theme": {k for k, _ in THEMES},
    "appearance": {"light", "dark"},
    "language": {"auto", "en", "ur", "roman_ur"},
    "response_style": {"balanced", "concise", "detailed"},
    "voice_lang": {"en-US", "ur-PK"},
}
BOOLS = {"memory_enabled", "auto_speak", "reduce_motion", "voice_responses", "voice_greeting", "voice_auto_submit"}
RANGES = {"voice_rate": (0.5, 2.0), "voice_volume": (0.0, 1.0)}


def profile_dict():
    return {"display_name": current_user.display_name, "email": current_user.email,
            "initials": current_user.initials, "avatar_url": current_user.avatar_url,
            "member_since": iso(current_user.created_at)}


@bp.get("/settings")
@login_required
def get_settings():
    return jsonify(settings=current_user.prefs.to_dict(), profile=profile_dict())


@bp.patch("/settings")
@login_required
def update_settings():
    data, prefs = request.get_json(silent=True) or {}, current_user.prefs
    for key, value in data.items():
        if key in CHOICES:
            if value not in CHOICES[key]:
                return jsonify(error=f"Invalid value for {key}."), 400
            setattr(prefs, key, value)
        elif key in BOOLS:
            if not isinstance(value, bool):
                return jsonify(error=f"{key} must be true or false."), 400
            setattr(prefs, key, value)
        elif key in RANGES:
            lo, hi = RANGES[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
                return jsonify(error=f"{key} must be between {lo} and {hi}."), 400
            setattr(prefs, key, float(value))
        elif key == "voice_name":
            if not isinstance(value, str) or len(value) > 200:
                return jsonify(error="Invalid voice name."), 400
            prefs.voice_name = value
        elif key == "custom_colors":
            clean, err = validate_custom(value)
            if err:
                return jsonify(error=err), 400
            prefs.custom_colors = json.dumps(clean) if clean else None
    db.session.commit()
    return jsonify(settings=prefs.to_dict())
