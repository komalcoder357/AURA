"""Custom-colour validation (hex + WCAG contrast) and the per-user theme stylesheet."""
import re

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
KEYS = ("bg", "accent", "card", "text")
MIN_CONTRAST = 4.5


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a, b, t):
    """t = share of colour a."""
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(round(x * t + y * (1 - t)) for x, y in zip(ra, rb))


def validate_custom(colors):
    """Returns (clean_dict | None, error | None). None colours means 'reset'."""
    if colors is None:
        return None, None
    if not isinstance(colors, dict) or set(colors) != set(KEYS):
        return None, "Provide all four colours: background, accent, card and text."
    clean = {}
    for k in KEYS:
        v = colors[k]
        if not isinstance(v, str) or not HEX_RE.match(v):
            return None, f"{k} must be a HEX colour like #FFAABB."
        clean[k] = v.lower()
    if contrast(clean["text"], clean["card"]) < MIN_CONTRAST or contrast(clean["text"], clean["bg"]) < MIN_CONTRAST:
        return None, "Text colour is too close to the background or card colour. Choose more contrast (at least 4.5:1)."
    return clean, None


def build_css(colors):
    if not colors:
        return "/* no custom colours */\n"
    bg, acc, card, text = colors["bg"], colors["accent"], colors["card"], colors["text"]
    on_acc = "#ffffff" if contrast("#ffffff", acc) >= contrast("#111111", acc) else "#111111"
    vars_ = {
        "--bg": bg, "--surface": card, "--text": text, "--accent": acc, "--accent-strong": acc,
        "--on-accent": on_acc, "--surface-2": mix(acc, card, .14), "--accent-soft": mix(acc, card, .3),
        "--muted": mix(text, bg, .72), "--border": mix(acc, bg, .28), "--bubble-user": mix(acc, card, .3),
        "--mascot-body": mix(acc, "#ffffff", .35), "--mascot-ear": mix(acc, "#ffffff", .6),
    }
    body = ";".join(f"{k}:{v}" for k, v in vars_.items())
    return f'html[data-custom="1"]{{{body}}}\n'
