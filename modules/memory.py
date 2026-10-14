"""Long-term memory: small, user-controlled facts. Retrieval = keyword overlap (no embeddings)."""
import re

from extensions import db
from models import MemoryRecord
from modules.language import tokens

STOP = {"the", "a", "an", "is", "am", "are", "to", "of", "and", "i", "my", "me", "you", "it", "in", "on",
        "for", "that", "this", "with", "ka", "ki", "ke", "hai", "main", "mujhe", "mera", "meri", "ko", "se"}
EXPLICIT = [
    re.compile(r"^\s*(?:please\s+)?remember(?:\s+that)?[:\s]+(.+)$", re.IGNORECASE | re.DOTALL),
    re.compile(r"^\s*yaad\s+rakh(?:o|na)(?:\s+(?:ke|k))?[:\s]+(.+)$", re.IGNORECASE | re.DOTALL),
]


def extract_explicit_memory(text):
    for pattern in EXPLICIT:
        match = pattern.match(text)
        if match:
            return match.group(1).strip()[:300] or None
    return None


def add_memory(user, content, max_items=100):
    content = " ".join(content.split())[:300]
    if not content:
        return None
    existing = [m for m in user.memories if m.content.lower() == content.lower()]
    if existing:
        return existing[0]
    if len(user.memories) >= max_items:
        return None
    record = MemoryRecord(user_id=user.id, content=content)
    db.session.add(record)
    db.session.flush()
    return record


def retrieve(user, query, k=4):
    if not user.prefs or not user.prefs.memory_enabled:
        return []
    q = {t for t in tokens(query) if t not in STOP}
    scored = []
    for rec in user.memories:
        overlap = len(q & {t for t in tokens(rec.content) if t not in STOP})
        if overlap:
            scored.append((overlap, rec.id, rec))
    scored.sort(key=lambda s: (-s[0], -s[1]))
    return [rec for _, _, rec in scored[:k]]
