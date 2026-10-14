import re
import time

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from models import User, UserPreferences

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_failures = {}  # (email, ip) -> [timestamps]; in-memory throttle, per process
MAX_FAILS, WINDOW = 5, 300
LOGIN_ERROR = "Unable to sign in with those details. Please check your email and password and try again."
REGISTER_ERROR = "We couldn't create an account with those details. Try signing in, or use a different email."


def _throttled(key):
    now = time.time()
    _failures[key] = [t for t in _failures.get(key, []) if now - t < WINDOW]
    return len(_failures[key]) >= MAX_FAILS


def _payload():
    return request.get_json(silent=True) or {} if request.is_json else request.form


def _respond(template, status, error=None, field_errors=None, values=None, ok_redirect=None):
    if request.is_json:
        if ok_redirect:
            return jsonify(ok=True, redirect=ok_redirect)
        return jsonify(ok=False, error=error, field_errors=field_errors or {}), status
    if ok_redirect:
        return redirect(ok_redirect)
    return render_template(template, error=error, field_errors=field_errors or {}, values=values or {}), status


def validate_registration(name, email, password, confirm):
    errs = {}
    if not name:
        errs["display_name"] = "Enter a display name."
    if not EMAIL_RE.match(email):
        errs["email"] = "Enter a valid email address."
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errs["password"] = "Use at least 8 characters with a letter and a number."
    if password != confirm:
        errs["confirm_password"] = "The two passwords don't match."
    return errs


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("register.html", error=None, field_errors={}, values={})
    f = _payload()
    name = " ".join(str(f.get("display_name", "")).split())[:60]
    email = str(f.get("email", "")).strip().lower()
    password, confirm = str(f.get("password", "")), str(f.get("confirm_password", ""))
    values = {"display_name": name, "email": email}  # never echo passwords
    errs = validate_registration(name, email, password, confirm)
    if errs:
        return _respond("register.html", 400, "Please fix the highlighted fields.", errs, values)
    if User.query.filter_by(email=email).first():
        return _respond("register.html", 400, REGISTER_ERROR, {}, values)
    user = User(email=email, display_name=name)
    user.set_password(password)
    user.prefs = UserPreferences()
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return _respond("register.html", 200, ok_redirect=url_for("index"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("login.html", error=None, field_errors={}, values={})
    f = _payload()
    email = str(f.get("email", "")).strip().lower()
    password = str(f.get("password", ""))
    values = {"email": email}
    errs = {}
    if not email:
        errs["email"] = "Enter your email."
    if not password:
        errs["password"] = "Enter your password."
    if errs:
        return _respond("login.html", 400, "Please fill in both fields.", errs, values)
    key = (email, request.remote_addr)
    if _throttled(key):
        return _respond("login.html", 429, "Too many attempts. Wait a few minutes and try again.", {}, values)
    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        _failures.pop(key, None)
        login_user(user)
        return _respond("login.html", 200, ok_redirect=url_for("index"))
    _failures.setdefault(key, []).append(time.time())
    return _respond("login.html", 401, LOGIN_ERROR, {}, values)  # same message for unknown email and wrong password


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
