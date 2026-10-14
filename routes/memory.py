from flask import Blueprint, abort, current_app, jsonify, request
from flask_login import current_user, login_required

from extensions import db
from models import MemoryRecord
from modules.memory import add_memory

bp = Blueprint("memory", __name__, url_prefix="/api/memory")


@bp.get("")
@login_required
def list_memory():
    items = sorted(current_user.memories, key=lambda m: m.id, reverse=True)
    return jsonify(enabled=current_user.prefs.memory_enabled, items=[m.to_dict() for m in items])


@bp.post("")
@login_required
def create_memory():
    content = ((request.get_json(silent=True) or {}).get("content") or "").strip()
    if not content:
        return jsonify(error="Memory cannot be empty."), 400
    record = add_memory(current_user, content, current_app.config["MAX_MEMORY_ITEMS"])
    if record is None:
        return jsonify(error="Memory limit reached. Delete an item first."), 400
    db.session.commit()
    return jsonify(item=record.to_dict()), 201


@bp.delete("/<public_id>")
@login_required
def delete_memory(public_id):
    rec = MemoryRecord.query.filter_by(public_id=public_id, user_id=current_user.id).first()
    if rec is None:
        abort(404)
    db.session.delete(rec)
    db.session.commit()
    return jsonify(ok=True)


@bp.delete("")
@login_required
def clear_memory():
    MemoryRecord.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify(ok=True)
