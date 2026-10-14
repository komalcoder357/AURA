import re

from flask import Blueprint, Response, abort, current_app, jsonify, request
from flask_login import current_user, login_required

from extensions import db

bp = Blueprint("profile", __name__, url_prefix="/api")
CTRL = re.compile(r"[\x00-\x1f\x7f]")


def sniff_image(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@bp.patch("/profile")
@login_required
def update_profile():
    name = CTRL.sub("", str((request.get_json(silent=True) or {}).get("display_name", ""))).strip()
    name = " ".join(name.split())
    if not name:
        return jsonify(error="Name cannot be empty."), 400
    if len(name) > 60:
        return jsonify(error="Name must be 60 characters or fewer."), 400
    current_user.display_name = name
    db.session.commit()
    return jsonify(display_name=name, initials=current_user.initials)


@bp.post("/profile/avatar")
@login_required
def upload_avatar():
    f = request.files.get("avatar")
    if f is None:
        return jsonify(error="Choose an image first."), 400
    data = f.read(current_app.config["MAX_AVATAR_BYTES"] + 1)
    if len(data) > current_app.config["MAX_AVATAR_BYTES"]:
        return jsonify(error="Image is too large (max 300 KB)."), 400
    mime = sniff_image(data)  # content is checked, the file name / declared type is not trusted
    if not mime:
        return jsonify(error="Use a PNG, JPEG or WebP image."), 400
    current_user.avatar_blob, current_user.avatar_mime = data, mime
    current_user.avatar_version = (current_user.avatar_version or 0) + 1
    db.session.commit()
    return jsonify(avatar_url=current_user.avatar_url)


@bp.delete("/profile/avatar")
@login_required
def delete_avatar():
    current_user.avatar_blob = current_user.avatar_mime = None
    current_user.avatar_version = (current_user.avatar_version or 0) + 1
    db.session.commit()
    return jsonify(ok=True)


@bp.get("/avatar")
@login_required
def get_avatar():  # always the logged-in user's own avatar; no id parameter exists
    if not current_user.avatar_blob:
        abort(404)
    return Response(current_user.avatar_blob, mimetype=current_user.avatar_mime,
                    headers={"Cache-Control": "private, max-age=3600"})
