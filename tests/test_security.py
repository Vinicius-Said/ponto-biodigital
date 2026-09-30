import json
import re
import pytest
from sqlalchemy import select
from app import create_app
from app.extensions import db
from app.models import AuditLog, Employee, SystemState, User
from conftest import PASSWORD


def test_bootstrap_requires_token_and_disables_after_completion(client, app):
    assert client.get("/setup").status_code == 200
    payload = {"username": "primeiro", "password": PASSWORD, "confirm": PASSWORD, "token": "wrong"}
    assert "Token de configuração inválido" in client.post("/setup", data=payload).text
    with app.app_context():
        assert db.session.scalar(select(User.id)) is None
    payload["token"] = app.config["SETUP_TOKEN"]
    assert client.post("/setup", data=payload).status_code == 302
    assert client.get("/setup").status_code == 404
    with app.app_context():
        assert db.session.get(SystemState, 1).setup_completed
        user = db.session.scalar(select(User))
        assert user.role == "DIRETORIA" and user.password_hash != PASSWORD
        assert user.check_password(PASSWORD)


def test_missing_setup_token_does_not_open_registration(client, app):
    app.config["SETUP_TOKEN"] = ""
    assert client.get("/setup").status_code == 503


def test_login_success_and_invalid_login(client, login):
    assert "Olá, Ana" in login().text
    client.post("/logout")
    assert (
        "Usuário ou senha inválidos"
        in client.post("/login", data={"username": "ana", "password": "invalid"}, follow_redirects=True).text
    )
    assert client.get("/dashboard/").status_code == 302


@pytest.mark.parametrize(
    "url",
    [
        "/employees/",
        "/admin/users",
        "/admin/schedules",
        "/admin/holidays",
        "/audit/",
        "/reports/",
        "/reports/pdf",
        "/corrections/adjust/1",
    ],
)
def test_employee_cannot_access_admin_routes(url, client, login):
    login()
    assert client.get(url).status_code == 403


@pytest.mark.parametrize("url", ["/dashboard/", "/attendance/", "/employees/", "/corrections/", "/reports/", "/audit/"])
def test_anonymous_cannot_access_protected_routes(url, client, system):
    assert client.get(url).status_code == 302


def test_employee_ids_do_not_allow_other_history(client, login, system):
    login()
    assert client.get(f"/attendance/?employee_id={system['bruno']}").status_code == 404
    assert "Ana Teste" in client.get(f"/attendance/?employee_id={system['ana']}").text


def test_csrf_is_global_for_login_setup_logout_and_mutations(client, app, system):
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/login", data={"username": "ana", "password": PASSWORD}).status_code == 400
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', client.get("/login").text).group(1)
    assert client.post("/login", data={"username": "ana", "password": PASSWORD, "csrf_token": token}).status_code == 302
    assert client.post("/logout").status_code == 400
    assert client.post("/attendance/register", data={"type": "ENTRADA"}).status_code == 400


def test_password_reset_revokes_old_session(app, client, login, system):
    login()
    admin = app.test_client()
    admin.post("/login", data={"username": "diretor", "password": PASSWORD})
    response = admin.post(
        f"/admin/users/{system['ana_user']}/password",
        data={"password": "new-test-password-2026", "confirm": "new-test-password-2026"},
    )
    assert response.status_code == 302
    assert client.get("/dashboard/").status_code == 302
    client.post("/logout")
    assert client.post("/login", data={"username": "ana", "password": PASSWORD}).status_code == 200
    assert client.post("/login", data={"username": "ana", "password": "new-test-password-2026"}).status_code == 302


def test_inactive_employee_cannot_login_even_with_active_user(app, client, system):
    with app.app_context():
        db.session.get(Employee, system["ana"]).active = False
        db.session.commit()
    assert client.post("/login", data={"username": "ana", "password": PASSWORD}).status_code == 200
    assert client.get("/dashboard/").status_code == 302


def test_deactivation_revokes_existing_session(app, client, login, system):
    login()
    admin = app.test_client()
    admin.post("/login", data={"username": "diretor", "password": PASSWORD})
    admin.post(f"/employees/{system['ana']}/status", data={"action": "deactivate"})
    assert client.get("/dashboard/").status_code == 302


def test_director_cannot_deactivate_last_director(app, client, login, system):
    login("diretor")
    assert (
        "outro diretor"
        in client.post(
            f"/admin/users/{system['director']}/status", data={"action": "deactivate"}, follow_redirects=True
        ).text
    )
    with app.app_context():
        assert db.session.get(User, system["director"]).active


def test_login_throttles_after_five_failures(client, system):
    for _ in range(5):
        assert client.post("/login", data={"username": "ana", "password": "wrong"}).status_code == 200
    assert client.post("/login", data={"username": "ana", "password": PASSWORD}).status_code == 429


def test_security_headers_and_post_only_logout(client, login):
    login()
    response = client.get("/dashboard/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert "form-action 'self'" in response.headers["Content-Security-Policy"]
    assert client.get("/logout").status_code == 405


def test_secrets_cannot_use_fallback_and_production_requires_mysql():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"SECRET_KEY": "short"})
    with pytest.raises(RuntimeError, match="MySQL"):
        create_app(
            {
                "SECRET_KEY": "a" * 48,
                "APP_ENV": "production",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SESSION_COOKIE_SECURE": True,
            }
        )


def test_password_never_appears_in_audit(app, client, login, system):
    login("diretor")
    client.post(f"/admin/users/{system['ana_user']}/password", data={"password": PASSWORD, "confirm": PASSWORD})
    with app.app_context():
        logs = [json.dumps(log.details) for log in db.session.scalars(select(AuditLog))]
        assert not any(PASSWORD in details for details in logs)


def test_malicious_name_is_escaped(app, client, login, system):
    login("diretor")
    payload = "<script>alert(1)</script>"
    client.post(f"/employees/{system['ana']}/edit", data={"name": payload})
    response = client.get("/employees/")
    assert payload not in response.text
    assert "&lt;script&gt;" in response.text


def test_sql_injection_username_does_not_authenticate(client, system):
    client.post("/login", data={"username": "' OR 1=1 --", "password": PASSWORD})
    assert client.get("/dashboard/").status_code == 302


def test_script_name_preserves_subpath_for_forms_and_assets(client, login):
    login()
    response = client.get("/dashboard/", environ_overrides={"SCRIPT_NAME": "/ponto"})
    assert "/ponto/static/css/app.css" in response.text
    assert 'action="/ponto/attendance/register"' in response.text
