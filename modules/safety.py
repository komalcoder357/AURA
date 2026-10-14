"""Layered safety screen (English, Urdu, Roman Urdu).

level "high"     : direct statements of intent / plan -> safety_support strategy.
level "possible" : indirect hopelessness / burden language -> supportive strategy plus a gentle direct check-in.
Ordinary sadness or frustration, and figures of speech ("kill this bug"), are NOT flagged.
Keyword and pattern based, so it WILL miss cases and cannot replace human help. See docs/limitations.md."""
import re

HIGH = [
    r"\b(kill(ing)? myself|end(ing)? my (own )?life|take my (own )?life|suicid\w*|self[- ]?harm|hurt(ing)? myself|"
    r"cut(ting)? myself|overdose on purpose)\b",
    r"\bi (want|wanna|am going|\'?m going|plan|am planning|\'?m planning) to (die|kill myself|end it( all)?)\b",
    r"\bi (don'?t|do not) want to (live|be alive|be here anymore)\b",
    r"\b(khudkushi|khud kushi|apni jaan (le|dena|de)\w*|mar jana chahta|mar jana chahti|marna chahta|marna chahti|"
    r"jeena nahi chahta|jeena nahi chahti)\b",
    r"(خودکشی|خود کشی|مرنا چاہتا|مرنا چاہتی|جینا نہیں چاہتا|جینا نہیں چاہتی|اپنی جان لے|اپنی جان دے)",
]
POSSIBLE = [
    r"\b(better off without me|everyone would be better (off )?if i (was|were) (gone|dead)|no (point|reason) (in|to) (living|go on)|"
    r"can'?t (go on|do this anymore|take it anymore)|wish i (would not|wouldn'?t|never) wake up|wish i (was|were) dead|"
    r"i('?m| am) (a )?burden|nobody would (miss|notice) me|tired of (living|being alive)|want it all to (end|stop))\b",
    r"\b(sab khatam (kar|ho)|thak gaya hoon? zindagi|zindagi se thak|main bojh hun|mere bina sab behtar|"
    r"koi fark nahi parta agar main na (rahu|rahun))\b",
    r"(زندگی سے تھک|میرے بغیر سب بہتر|بوجھ ہوں|سب ختم کر)",
]
BENIGN = re.compile(r"\b(kill(ing)? (this|the|that|my) (bug|process|time|app|task)|dying (to|of laughter)|dead (tired|serious)|"
                    r"killed it|to die for)\b", re.IGNORECASE)
_H = [re.compile(p, re.IGNORECASE) for p in HIGH]
_P = [re.compile(p, re.IGNORECASE) for p in POSSIBLE]


def check_safety(text, distress=None):
    """Returns {'flag': bool, 'level': 'high'|'possible'|None, 'category': str|None}."""
    clean = BENIGN.sub(" ", text)
    if any(p.search(clean) for p in _H):
        return {"flag": True, "level": "high", "category": "self_harm_language"}
    if any(p.search(clean) for p in _P):
        return {"flag": False, "level": "possible", "category": "hopelessness_language"}
    return {"flag": False, "level": None, "category": None}


def safety_message(extra_resources=""):
    msg = ("I'm really sorry you're going through this, and I'm glad you told me. I'm an AI and can't "
           "keep you safe, so please reach out right now to someone who can: a trusted person near you, "
           "or your local emergency number or crisis line. If you might act on these thoughts soon, call "
           "emergency services now. I'm here to keep talking with you too. Are you safe at this moment?")
    return f"{msg} {extra_resources}".strip()
