from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from threading import Barrier
import pytest
from sqlalchemy import select
from app.extensions import db
from app.models import CorrectionRequest, TimeRecord, User
from app.services.attendance import register_attendance
from app.services.corrections import request_correction
from app.services.validation import DomainError


def race(app, actor_id, action):
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("mysql"):
        pytest.skip("Row-lock concurrency requires MySQL/MariaDB/InnoDB.")
    barrier = Barrier(2)

    def worker():
        with app.app_context():
            # Authentication starts a read before waiting on the business lock.
            assert db.session.get(User, actor_id).is_active
            barrier.wait(timeout=10)
            try:
                action()
                db.session.commit()
                return "aplicado"
            except DomainError:
                db.session.rollback()
                return "bloqueado"

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(worker), executor.submit(worker)
        return sorted([first.result(timeout=15), second.result(timeout=15)])


def test_two_simultaneous_punches_create_only_one_record(app, system):
    assert race(
        app, system["ana_user"], lambda: register_attendance(system["ana"], "ENTRADA", "2026-09-30", "127.0.0.1")
    ) == ["aplicado", "bloqueado"]
    with app.app_context():
        assert len(list(db.session.scalars(select(TimeRecord)))) == 1


def test_two_simultaneous_requests_create_only_one_pending_request(app, system):
    assert race(
        app,
        system["ana_user"],
        lambda: request_correction(
            system["ana"], date(2026, 9, 29), "ENTRADA", time(8), "Marcação esquecida no dia anterior."
        ),
    ) == ["aplicado", "bloqueado"]
    with app.app_context():
        assert len(list(db.session.scalars(select(CorrectionRequest)))) == 1
