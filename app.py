import logging
import threading
from types import SimpleNamespace

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from config import THEMES, Config
from extensions import csrf, db, login_manager


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    logging.basicConfig(level=logging.INFO)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"

    import models
    from modules.ai_service import AIService
    from modules.emotion import EmotionAnalyzer
    import migrations
    from modules.theme import build_css
    from routes import auth, chat, memory, profile, settings

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(error="Please log in."), 401
        return redirect(url_for("auth.login"))

    app.extensions["aura"] = SimpleNamespace(
        emotion=EmotionAnalyzer.from_config(app.config), ai=AIService.from_config(app.config))
    for module in (auth, chat, memory, profile, settings):
        app.register_blueprint(module.bp)

    with app.app_context():
        db.create_all()
        added = migrations.run(app)
        if added:
            app.logger.info("Database upgraded, new columns: %s", ", ".join(added))

    if app.config["EMOTION_LOAD"] == "startup" and not app.config.get("TESTING"):
        threading.Thread(target=app.extensions["aura"].emotion.warmup, daemon=True).start()

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; media-src 'self' blob:; "
            "frame-ancestors 'none'; form-action 'self'")
        resp.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    

    @app.errorhandler(404)
    def not_found(_):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found."), 404

        return render_template(
            "login.html",
            error="Page not found.",
            values={},
            field_errors={},
        ), 404



    @app.errorhandler(400)
    def bad_request(err):
        if request.path.startswith("/api/"):
            return jsonify(error="Bad request (check your session and try again)."), 400
        return err

    @app.errorhandler(500)
    def server_error(_):
        if request.path.startswith("/api/"):
            return jsonify(error="Something went wrong on the server."), 500
        return "Something went wrong.", 500

    @app.route("/")
    def index():
        if not current_user.is_authenticated:
            return render_template("landing.html")
        return render_template("index.html", themes=THEMES, prefs=current_user.prefs,
                               welcome=app.config["WELCOME_TEXT"])

    @app.route("/theme.css")
    def theme_css():
        css = build_css(current_user.prefs.colors) if current_user.is_authenticated and current_user.prefs else "/* anonymous */\n"
        return app.response_class(css, mimetype="text/css", headers={"Cache-Control": "no-store"})

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    return app


if __name__ == "__main__":
    create_app().run(debug=False, port=5000)
