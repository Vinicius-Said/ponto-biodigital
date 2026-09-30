import hashlib
import secrets
from datetime import timedelta
from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, select
from app.extensions import db
from app.forms import LoginForm, OwnPasswordForm, SetupForm
from app.models import LoginAttempt, SystemState, User
from app.services.audit import write_audit
from app.services.clock import utc_now
from app.services.schedules import seed_schedules
from . import auth_bp


def setup_finished():
    state = db.session.get(SystemState, 1)
    return bool(state and state.setup_completed)


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    if setup_finished() or db.session.scalar(select(User.id).limit(1)):
        abort(404)
    token = current_app.config["SETUP_TOKEN"]
    if len(token) < 32:
        return render_template(
            "error.html",
            code=503,
            message="Configure um SETUP_TOKEN aleatório com pelo menos 32 caracteres para habilitar o primeiro acesso.",
        ), 503
    form = SetupForm()
    if form.validate_on_submit():
        if not secrets.compare_digest(form.token.data, token):
            form.token.errors.append("Token de configuração inválido.")
        else:
            state = db.session.scalar(
                select(SystemState)
                .where(SystemState.id == 1)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if state is None:
                abort(503, description="Execute as migrações antes da configuração inicial.")
            if state.setup_completed or db.session.scalar(select(User.id).limit(1)):
                abort(404)
            user = User(username=form.username.data, role="DIRETORIA")
            user.set_password(form.password.data)
            db.session.add(user)
            seed_schedules()
            db.session.flush()
            state.setup_completed = True
            write_audit("CONFIGURAR_SISTEMA", "users", user.id, {"usuario": user.username}, actor_id=user.id)
            db.session.commit()
            flash("Primeiro diretor criado. Faça login para começar.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/setup.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if not setup_finished():
        return redirect(url_for("auth.setup"))
    form = LoginForm()
    if form.validate_on_submit():
        digest = hashlib.sha256(form.username.data.encode()).hexdigest()
        recent = utc_now() - timedelta(minutes=15)
        failures = db.session.scalar(
            select(func.count(LoginAttempt.id)).where(
                LoginAttempt.ip_address == (request.remote_addr or "unknown"),
                LoginAttempt.username_digest == digest,
                LoginAttempt.created_at >= recent,
            )
        )
        ip_failures = db.session.scalar(
            select(func.count(LoginAttempt.id)).where(
                LoginAttempt.ip_address == (request.remote_addr or "unknown"), LoginAttempt.created_at >= recent
            )
        )
        if failures >= 5 or ip_failures >= 30:
            flash("Muitas tentativas. Aguarde 15 minutos e tente novamente.", "error")
            return render_template("auth/login.html", form=form), 429
        user = db.session.scalar(select(User).where(User.username == form.username.data))
        valid = user.check_password(form.password.data) if user else False
        if user and valid and user.is_active:
            session.clear()
            login_user(user, remember=False)
            session.permanent = True
            session["session_version"] = user.session_version
            write_audit("LOGIN", "users", user.id, {"resultado": "sucesso"})
            db.session.commit()
            return redirect(url_for("dashboard.index"))
        db.session.add(LoginAttempt(ip_address=request.remote_addr or "unknown", username_digest=digest))
        write_audit("LOGIN_INVALIDO", details={"resultado": "falha"})
        db.session.commit()
        flash("Usuário ou senha inválidos.", "error")
    return render_template("auth/login.html", form=form)


@auth_bp.post("/logout")
@login_required
def logout():
    write_audit("LOGOUT", "users", current_user.id)
    db.session.commit()
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/password", methods=["GET", "POST"])
@login_required
def password():
    form = OwnPasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("A senha atual está incorreta.")
        else:
            current_user.set_password(form.password.data)
            write_audit("ALTERAR_PROPRIA_SENHA", "users", current_user.id)
            db.session.commit()
            logout_user()
            session.clear()
            flash("Senha alterada. Faça login novamente.", "success")
            return redirect(url_for("auth.login"))
    return render_template(
        "form.html",
        title="Alterar minha senha",
        subtitle="Ao salvar, todas as suas sessões serão encerradas.",
        form=form,
    )
