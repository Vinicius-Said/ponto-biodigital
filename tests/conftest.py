import os
from datetime import date, datetime
from pathlib import Path
import importlib
import pytest
from flask_migrate import upgrade
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app import create_app
from app.extensions import db
from app.models import Employee, EmployeeSchedule, SystemState, User
from app.services.schedules import seed_schedules

PASSWORD = "test-only-password-2026"
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def clock(monkeypatch):
    current = [datetime(2026, 9, 30, 20, 0)]
    for name in ["clock", "attendance", "corrections", "time_calculator", "history", "schedules", "audit"]:
        module = importlib.import_module("app.services." + name)
        if hasattr(module, "utc_now"):
            monkeypatch.setattr(module, "utc_now", lambda: current[0])
    for name in ["app.auth.routes", "app.dashboard.routes"]:
        module = importlib.import_module(name)
        if hasattr(module, "utc_now"):
            monkeypatch.setattr(module, "utc_now", lambda: current[0])

    def set_time(value):
        current[0] = datetime.fromisoformat(value) if isinstance(value, str) else value
        return current[0]

    return set_time


@pytest.fixture
def app(tmp_path, clock):
    database = os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    if not make_url(database).drivername.startswith("sqlite") and not (make_url(database).database or "").startswith(
        "ponto_test"
    ):
        raise RuntimeError("Tests can only reset MySQL/MariaDB databases named ponto_test*.")
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret-key-aaaaaaaaaaaaaaaaaaaaaaaa",
            "SETUP_TOKEN": "test-only-setup-token-bbbbbbbbbbbbbbbbbbbbbb",
            "APP_ENV": "development",
            "SQLALCHEMY_DATABASE_URI": database,
            "SESSION_COOKIE_SECURE": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        if os.getenv("TEST_DATABASE_URL"):
            db.metadata.drop_all(db.engine)
            db.session.execute(text("DROP TABLE IF EXISTS alembic_version"))
            db.session.commit()
        upgrade(directory=str(ROOT / "migrations"))
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def system(app):
    with app.app_context():
        seed_schedules()
        from app.models import Schedule

        full = db.session.scalar(
            db.select(Schedule).where(Schedule.interval_minutes == 60).order_by(Schedule.start_time)
        )
        short = db.session.scalar(db.select(Schedule).where(Schedule.interval_minutes == 0))
        director = User(username="diretor", role="DIRETORIA")
        director.set_password(PASSWORD)
        first = Employee(name="Ana Teste", hired_on=date(2026, 9, 1))
        second = Employee(name="Bruno Teste", hired_on=date(2026, 9, 1))
        db.session.add_all([director, first, second])
        db.session.flush()
        one = User(username="ana", role="FUNCIONARIO", employee_id=first.id)
        two = User(username="bruno", role="FUNCIONARIO", employee_id=second.id)
        one.set_password(PASSWORD)
        two.set_password(PASSWORD)
        db.session.add_all(
            [
                one,
                two,
                EmployeeSchedule(employee_id=first.id, schedule_id=full.id, valid_from=first.hired_on),
                EmployeeSchedule(employee_id=second.id, schedule_id=short.id, valid_from=second.hired_on),
            ]
        )
        db.session.get(SystemState, 1).setup_completed = True
        db.session.commit()
        return {
            "director": director.id,
            "ana": first.id,
            "bruno": second.id,
            "ana_user": one.id,
            "full": full.id,
            "short": short.id,
        }


@pytest.fixture
def login(client, system):
    def sign_in(username="ana"):
        client.post("/logout")
        return client.post("/login", data={"username": username, "password": PASSWORD}, follow_redirects=True)

    return sign_in
