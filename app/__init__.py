from pathlib import Path
from flask import Flask, redirect, render_template, request, session, url_for
from flask_login import current_user, logout_user
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import configuration
from app.extensions import csrf, db, login_manager, migrate


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(configuration())
    if test_config:
        app.config.update(test_config)
    secret = app.config.get("SECRET_KEY")
    if not secret or len(secret) < 32 or secret in {"change-this-key", "change-me"}:
        raise RuntimeError("Defina SECRET_KEY aleatória com pelo menos 32 caracteres no .env ou no ambiente.")
    if app.config["APP_ENV"] == "production":
        if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("mysql+pymysql://"):
            raise RuntimeError("Use MySQL/MariaDB (mysql+pymysql://) em produção.")
        if not app.config["SESSION_COOKIE_SECURE"]:
            raise RuntimeError("SESSION_COOKIE_SECURE precisa ser true em produção.")
        app.config["DEBUG"] = False
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("mysql"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"]["isolation_level"] = "READ COMMITTED"
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para continuar."
    login_manager.login_message_category = "info"
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(User, int(user_id))
            return user if user and user.is_active else None
        except (TypeError, ValueError):
            return None

    @app.before_request
    def validate_session():
        if current_user.is_authenticated and session.get("session_version") != current_user.session_version:
            logout_user()
            session.clear()
            return redirect(url_for("auth.login"))

    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.employees import employees_bp
    from app.attendance import attendance_bp
    from app.corrections import corrections_bp
    from app.admin import admin_bp
    from app.audit import audit_bp
    from app.reports import reports_bp

    for blueprint in (
        auth_bp,
        dashboard_bp,
        employees_bp,
        attendance_bp,
        corrections_bp,
        admin_bp,
        audit_bp,
        reports_bp,
    ):
        app.register_blueprint(blueprint)

    @app.get("/")
    def index():
        return redirect(url_for("dashboard.index" if current_user.is_authenticated else "auth.login"))

    @app.get("/health")
    def health():
        return {"status": "ok", "application": "ponto-biodigital", "version": "0.1.0"}

    from app.services.clock import datetime_label, local_time, today
    from app.services.time_calculator import format_duration
    from app.models.time_record import RECORD_LABELS, RECORD_TYPES

    app.jinja_env.filters.update(duration=format_duration, local_time=local_time, datetime_label=datetime_label)

    @app.context_processor
    def common_values():
        return {"record_labels": RECORD_LABELS, "record_types": RECORD_TYPES, "current_date": today()}

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        if app.config["APP_ENV"] == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template(
            "error.html", code=400, message="Formulário expirado ou inválido. Atualize a página e tente novamente."
        ), 400

    @app.errorhandler(IntegrityError)
    def integrity_error(error):
        db.session.rollback()
        return render_template(
            "error.html",
            code=409,
            message="Os dados já existem ou foram alterados em outra sessão. Atualize a página e tente novamente.",
        ), 409

    @app.errorhandler(OperationalError)
    def database_error(error):
        db.session.rollback()
        app.logger.error("Falha de acesso ao banco. Verifique conexão e migrações.")
        return render_template(
            "error.html",
            code=503,
            message="Banco de dados indisponível. Verifique a conexão e se as migrações foram executadas.",
        ), 503

    for code in (400, 403, 404, 405, 413, 500):

        def handler(error, code=code):
            if code == 500:
                db.session.rollback()
            messages = {
                400: "Solicitação inválida.",
                403: "Você não possui permissão para acessar esta página.",
                404: "Página ou registro não encontrado.",
                405: "Essa ação não está disponível por este método.",
                413: "Os dados enviados excedem o limite permitido.",
                500: "Não foi possível concluir a operação. Tente novamente.",
            }
            return render_template(
                "error.html", code=code, message=error.description if code == 400 else messages[code]
            ), code

        app.register_error_handler(code, handler)
    counts = [app.config[key] for key in ("PROXY_FOR_COUNT", "PROXY_PROTO_COUNT", "PROXY_PREFIX_COUNT")]
    if any(counts):
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=counts[0], x_proto=counts[1], x_prefix=counts[2], x_host=0, x_port=0
        )
    from app.cli import register_commands

    register_commands(app)
    return app
