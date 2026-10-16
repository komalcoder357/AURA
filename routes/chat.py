
import json
import time
from datetime import timedelta

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    request,
    stream_with_context,
)
from flask_login import current_user, login_required

from extensions import db
from models import Conversation, Message, utcnow
from modules import memory as mem
from modules.ai_service import (
    AIUnavailable,
    build_system_prompt,
    fallback_reply,
)
from modules.decision_engine import decide
from modules.distress import distress_signal
from modules.language import detect_language, normalize
from modules.safety import check_safety


bp = Blueprint("chat", __name__, url_prefix="/api")

RETRYABLE_SOURCES = ("fallback", "safety_template", "partial")
VALID_INPUT_SOURCES = ("typed", "voice")


def _svc():
    return current_app.extensions["aura"]


def _own(public_id):
    conv = Conversation.query.filter_by(
        public_id=public_id,
        user_id=current_user.id,
    ).first()

    if conv is None:
        abort(404)

    return conv


def _title_from(text):
    title = " ".join(text.split())
    return (
        title[:42].rstrip() + "…"
        if len(title) > 42
        else title or "New chat"
    )


def _observations(conv):
    obs = []

    for m in conv.messages:
        if m.role == "user" and m.analysis:
            a = m.analysis

            obs.append({
                "turn": len(obs) + 1,
                "emotion": a.get("emotion"),
                "confidence": a.get("emotion_confidence"),
                "status": a.get("analysis_status"),
                "method": a.get("analysis_method"),
                "language": a.get("language"),
                "analysis_status": a.get("analysis_status"),
                "analysis_method": a.get("analysis_method"),
                "emotion_confidence": a.get("emotion_confidence"),
            })

    return obs


def _context(conv):
    rows = [
        {"role": m.role, "content": m.content}
        for m in conv.messages
    ]

    if rows and rows[-1]["role"] == "user":
        rows = rows[:-1]

    return rows[-current_app.config["CONTEXT_MESSAGES"]:]


def _prepare(data):
    """Validate, analyse and store a user message."""
    cfg, svc = current_app.config, _svc()

    conv_id = data.get("conversation_id")
    memory_saved = None
    memory_note = None
    emotion_ms = 0.0

    if data.get("regenerate"):
        if not conv_id:
            return None, (
                jsonify(error="conversation_id is required"),
                400,
            )

        conv = _own(conv_id)

        if (
            conv.messages
            and conv.messages[-1].role == "assistant"
            and conv.messages[-1].source in RETRYABLE_SOURCES
        ):
            db.session.delete(conv.messages[-1])
            db.session.flush()
            db.session.refresh(conv)

        user_msg = (
            conv.messages[-1]
            if conv.messages and conv.messages[-1].role == "user"
            else None
        )

        if user_msg is None:
            return None, (
                jsonify(error="Nothing to retry."),
                400,
            )

        analysis = user_msg.analysis or {}
        decision = user_msg.decision or {
            "strategy": "casual",
            "reason_codes": [],
        }

        text = user_msg.content
        detected = analysis.get("language", "en")
        distress = analysis.get("distress")

        # Regeneration reuses the existing message and its saved source.
        input_source = user_msg.input_source or "typed"

    else:
        text = str(data.get("message") or "").strip()

        if not text:
            return None, (
                jsonify(error="Message is empty."),
                400,
            )

        if len(text) > cfg["MAX_MESSAGE_CHARS"]:
            return None, (
                jsonify(
                    error=(
                        f"Message is too long "
                        f"(max {cfg['MAX_MESSAGE_CHARS']} characters)."
                    )
                ),
                400,
            )

        # Backward-compatible default for existing text-chat requests.
        input_source = str(
            data.get("input_source") or "typed"
        ).strip().lower()

        if input_source not in VALID_INPUT_SOURCES:
            return None, (
                jsonify(
                    error=(
                        "input_source must be "
                        "'typed' or 'voice'."
                    )
                ),
                400,
            )

        conv = _own(conv_id) if conv_id else None

        if conv is None:
            conv = Conversation(
                user_id=current_user.id,
                title=_title_from(text),
            )
            db.session.add(conv)
            db.session.flush()

        language = detect_language(text)
        detected = language["code"]

        e0 = time.perf_counter()

        analysis = svc.emotion.analyze(
            normalize(text, detected),
            language,
        )

        emotion_ms = (time.perf_counter() - e0) * 1000

        safety = check_safety(text)

        distress = distress_signal(
            _observations(conv)
            + [{
                "emotion": analysis["emotion"],
                "emotion_confidence": analysis["emotion_confidence"],
                "analysis_status": analysis["analysis_status"],
                "analysis_method": analysis["analysis_method"],
            }]
        )

        decision = decide(
            text,
            analysis,
            safety,
            distress,
            cfg["EMOTION_MIN_CONFIDENCE"],
        )

        analysis["distress"] = distress

        if current_user.prefs.memory_enabled:
            # Save explicit memories only when requested by the user.
            note = mem.extract_explicit_memory(text)

            if note:
                record = mem.add_memory(
                    current_user,
                    note,
                    cfg["MAX_MEMORY_ITEMS"],
                )

                if record:
                    memory_saved = memory_note = record.content

        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=text,
            input_source=input_source,
            analysis_json=json.dumps(analysis),
            decision_json=json.dumps(decision),
        )

        db.session.add(user_msg)
        db.session.flush()

    prefs = current_user.prefs

    memories = [
        r.content
        for r in mem.retrieve(
            current_user,
            text,
            cfg["MEMORY_TOP_K"],
        )
    ]

    prompt = build_system_prompt(
        decision["strategy"],
        prefs.language,
        detected,
        memories,
        prefs.response_style,
        memory_note,
        risk_check=(
            "indirect_risk_language"
            in decision.get("reason_codes", [])
        ),
    )

    return {
        "conv": conv,
        "conv_id": conv.id,
        "user_msg": user_msg,
        "text": text,
        "input_source": input_source,
        "analysis": analysis,
        "decision": decision,
        "distress": distress,
        "memory_saved": memory_saved,
        "emotion_ms": emotion_ms,
        "history": _context(conv),
        "prompt": prompt,
    }, None


def _save_assistant(
    ctx,
    reply,
    source,
    error,
    ai_ms,
    ttft_ms=None,
):
    # Re-fetch the conversation in the active database session.
    conv = db.session.get(Conversation, ctx["conv_id"])

    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=reply,
        source=source,
        latency_ms=round(ai_ms),
        ttft_ms=(
            None if ttft_ms is None else round(ttft_ms)
        ),
        error_type=error,
    )

    db.session.add(msg)
    conv.updated_at = utcnow()
    db.session.commit()

    return msg


def _final_payload(ctx, msg, error, ai_ms, ttft_ms, t0):
    total = (time.perf_counter() - t0) * 1000

    current_app.logger.info(
        "chat timings emotion_ms=%.0f ttft_ms=%s "
        "ai_ms=%.0f total_ms=%.0f source=%s",
        ctx["emotion_ms"],
        "-" if ttft_ms is None else round(ttft_ms),
        ai_ms,
        total,
        msg.source,
    )

    conv = db.session.get(Conversation, ctx["conv_id"])

    return {
        "assistant_message": msg.to_dict(),
        "observations": _observations(conv),
        "retryable": msg.source in RETRYABLE_SOURCES,
        "error_type": error,
        "timings_ms": {
            "emotion": round(ctx["emotion_ms"]),
            "first_chunk": (
                None if ttft_ms is None else round(ttft_ms)
            ),
            "ai": round(ai_ms),
            "total": round(total),
        },
    }


def _meta_payload(ctx):
    return {
        "conversation": ctx["conv"].summary(),
        "user_message": ctx["user_msg"].to_dict(),
        "analysis": ctx["analysis"],
        "decision": ctx["decision"],
        "distress": ctx["distress"],
        "memory_saved": ctx["memory_saved"],
    }


@bp.post("/chat")
@login_required
def chat():
    t0 = time.perf_counter()

    ctx, err = _prepare(
        request.get_json(silent=True) or {}
    )

    if err:
        return err

    start = time.perf_counter()
    error = None
    ttft = None

    try:
        reply = _svc().ai.generate(
            ctx["text"],
            ctx["history"],
            ctx["prompt"],
        )
        source = "gemini"

    except Exception as exc:
        error = (
            str(exc)
            if isinstance(exc, AIUnavailable)
            else type(exc).__name__
        )

        current_app.logger.warning(
            "AI unavailable: %s",
            error,
        )

        reply, source = fallback_reply(
            ctx["decision"]["strategy"],
            current_app.config["SAFETY_RESOURCES"],
        )

    ai_ms = (time.perf_counter() - start) * 1000

    msg = _save_assistant(
        ctx,
        reply,
        source,
        error,
        ai_ms,
    )

    return jsonify({
        **_meta_payload(ctx),
        **_final_payload(
            ctx,
            msg,
            error,
            ai_ms,
            ttft,
            t0,
        ),
    })


@bp.post("/chat/stream")
@login_required
def chat_stream():
    """NDJSON stream: meta, delta chunks, and done."""
    t0 = time.perf_counter()

    ctx, err = _prepare(
        request.get_json(silent=True) or {}
    )

    if err:
        return err

    ctx["conv"].updated_at = utcnow()
    db.session.commit()

    svc = _svc()
    cfg = current_app.config
    meta = _meta_payload(ctx)

    def line(obj):
        return json.dumps(
            obj,
            ensure_ascii=False,
        ) + "\n"

    @stream_with_context
    def gen():
        yield line({
            "type": "meta",
            **meta,
        })

        parts = []
        ttft = None
        error = None
        source = "gemini"
        start = time.perf_counter()

        try:
            for chunk in svc.ai.stream(
                ctx["text"],
                ctx["history"],
                ctx["prompt"],
            ):
                if ttft is None:
                    ttft = (
                        time.perf_counter() - start
                    ) * 1000

                parts.append(chunk)

                yield line({
                    "type": "delta",
                    "text": chunk,
                })

        except GeneratorExit:
            # Preserve generated text if the client cancels.
            if parts:
                try:
                    _save_assistant(
                        ctx,
                        "".join(parts),
                        "partial",
                        "client_cancelled",
                        (time.perf_counter() - start) * 1000,
                        ttft,
                    )
                except Exception:
                    db.session.rollback()

            raise

        except Exception as exc:
            error = (
                str(exc)
                if isinstance(exc, AIUnavailable)
                else type(exc).__name__
            )

            current_app.logger.warning(
                "AI unavailable: %s",
                error,
            )

            if parts:
                source = "partial"
            else:
                reply, source = fallback_reply(
                    ctx["decision"]["strategy"],
                    cfg["SAFETY_RESOURCES"],
                )

                parts = [reply]

                yield line({
                    "type": "delta",
                    "text": reply,
                })

        if not parts:
            error = error or "empty_response"

            reply, source = fallback_reply(
                ctx["decision"]["strategy"],
                cfg["SAFETY_RESOURCES"],
            )

            parts = [reply]

            yield line({
                "type": "delta",
                "text": reply,
            })

        ai_ms = (time.perf_counter() - start) * 1000

        msg = _save_assistant(
            ctx,
            "".join(parts),
            source,
            error,
            ai_ms,
            ttft,
        )

        yield line({
            "type": "done",
            **_final_payload(
                ctx,
                msg,
                error,
                ai_ms,
                ttft,
                t0,
            ),
        })

    return Response(
        gen(),
        mimetype="application/x-ndjson",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@bp.get("/conversations")
@login_required
def list_conversations():
    rows = (
        Conversation.query
        .filter_by(user_id=current_user.id)
        .order_by(
            Conversation.pinned.desc(),
            Conversation.updated_at.desc(),
        )
        .all()
    )

    return jsonify(
        conversations=[c.summary() for c in rows]
    )


@bp.get("/conversations/<public_id>")
@login_required
def get_conversation(public_id):
    conv = _own(public_id)
    obs = _observations(conv)

    last_user = next(
        (
            m for m in reversed(conv.messages)
            if m.role == "user"
        ),
        None,
    )

    last = last_user.analysis if last_user else None

    return jsonify(
        conversation=conv.summary(),
        messages=[m.to_dict() for m in conv.messages],
        observations=obs,
        distress=distress_signal(obs),
        analysis=last,
        decision=(
            last_user.decision if last_user else None
        ),
    )


@bp.patch("/conversations/<public_id>")
@login_required
def update_conversation(public_id):
    conv = _own(public_id)
    data = request.get_json(silent=True) or {}

    if "pinned" in data:
        conv.pinned = bool(data["pinned"])

    if "title" in data:
        title = " ".join(
            str(data["title"]).split()
        )[:120]

        if not title:
            return jsonify(
                error="Title cannot be empty."
            ), 400

        conv.title = title

    db.session.commit()

    return jsonify(
        conversation=conv.summary()
    )


@bp.delete("/conversations/<public_id>")
@login_required
def delete_conversation(public_id):
    db.session.delete(_own(public_id))
    db.session.commit()

    return jsonify(ok=True)


@bp.delete("/conversations")
@login_required
def delete_all_conversations():
    for conv in Conversation.query.filter_by(
        user_id=current_user.id
    ).all():
        db.session.delete(conv)

    db.session.commit()

    return jsonify(ok=True)


def _snippet(text, q, width=70):
    i = text.lower().find(q.lower())

    if i < 0:
        return text[:width * 2]

    a = max(0, i - width // 2)
    b = min(len(text), i + len(q) + width)

    return (
        ("…" if a else "")
        + text[a:b].replace("\n", " ")
        + ("…" if b < len(text) else "")
    )


@bp.get("/search")
@login_required
def search():
    """Search only the current user's conversation data."""
    q = (request.args.get("q") or "").strip()[:100]

    if not q:
        return jsonify(results=[], query="")

    like = (
        "%"
        + q.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
        + "%"
    )

    results = []
    seen = set()

    conversations = (
        Conversation.query
        .filter(
            Conversation.user_id == current_user.id,
            Conversation.title.ilike(
                like,
                escape="\\",
            ),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(30)
    )

    for c in conversations:
        seen.add(c.id)

        results.append({
            **c.summary(),
            "match": "title",
            "snippet": c.title,
        })

    rows = (
        db.session.query(Message, Conversation)
        .join(
            Conversation,
            Message.conversation_id == Conversation.id,
        )
        .filter(
            Conversation.user_id == current_user.id,
            Message.content.ilike(
                like,
                escape="\\",
            ),
        )
        .order_by(Message.id.desc())
        .limit(60)
    )

    for m, c in rows:
        if c.id in seen:
            continue

        seen.add(c.id)

        results.append({
            **c.summary(),
            "match": "message",
            "snippet": _snippet(m.content, q),
        })

    return jsonify(
        results=results[:40],
        query=q,
    )


@bp.get("/analytics")
@login_required
def analytics():
    """Return measured analytics for the current user."""
    try:
        days = max(
            1,
            min(int(request.args.get("days", 30)), 365),
        )
    except (ValueError, TypeError):
        days = 30

    since = utcnow() - timedelta(days=days)

    rows = (
        db.session.query(Message)
        .join(
            Conversation,
            Message.conversation_id == Conversation.id,
        )
        .filter(
            Conversation.user_id == current_user.id,
            Message.created_at >= since,
        )
        .all()
    )

    per_day = {}
    emotions = {}
    strategies = {}
    sources = {}
    lat = []
    errors = {}

    input_sources = {
        "typed": 0,
        "voice": 0,
        "unknown": 0,
    }

    user_msgs = 0

    for m in rows:
        day = m.created_at.strftime("%Y-%m-%d")

        if m.role == "user":
            user_msgs += 1
            per_day[day] = per_day.get(day, 0) + 1

            input_source = m.input_source or "unknown"

            if input_source in ("typed", "voice"):
                input_sources[input_source] += 1
            else:
                input_sources["unknown"] += 1

            a = m.analysis or {}
            d = m.decision or {}

            if (
                a.get("emotion")
                and a.get("analysis_status")
                in ("success", "experimental")
            ):
                emotion = a["emotion"]
                emotions[emotion] = (
                    emotions.get(emotion, 0) + 1
                )

            if d.get("strategy"):
                strategy = d["strategy"]
                strategies[strategy] = (
                    strategies.get(strategy, 0) + 1
                )

        else:
            source = m.source or "unknown"
            sources[source] = sources.get(source, 0) + 1

            if (
                m.latency_ms is not None
                and m.source == "gemini"
            ):
                lat.append(m.latency_ms)

            if m.error_type:
                errors[m.error_type] = (
                    errors.get(m.error_type, 0) + 1
                )

    lat.sort()

    return jsonify(
        days=days,
        user_messages=user_msgs,
        activity_by_day=dict(sorted(per_day.items())),
        emotion_estimates=emotions,
        strategies=strategies,
        reply_sources=sources,
        input_sources=input_sources,
        provider_errors=errors,
        latency_ms={
            "count": len(lat),
            "average": (
                round(sum(lat) / len(lat))
                if lat else None
            ),
            "median": (
                lat[len(lat) // 2]
                if lat else None
            ),
            "max": lat[-1] if lat else None,
        },
    )
