from datetime import date, datetime
import pytest
from sqlalchemy import select
from app.extensions import db
from app.models import Employee, EmployeeSchedule, Schedule, User
from app.services.audit import retention_cutoff
from app.services.history import employee_history
from app.services.schedules import assign_schedule
from app.services.validation import DomainError


def test_create_employee_creates_hashed_login_and_assignment(app, client, login, system):
    login("diretor")
    response = client.post(
        "/employees/create",
        data={
            "name": "Carla Teste",
            "hired_on": "2026-09-30",
            "schedule_id": system["full"],
            "username": "carla",
            "password": "carla-test-password-2026",
        },
        follow_redirects=True,
    )
    assert "Carla Teste" in response.text
    with app.app_context():
        employee = db.session.scalar(select(Employee).where(Employee.name == "Carla Teste"))
        assert employee.users[0].check_password("carla-test-password-2026")
        assert employee.assignments[0].valid_from == date(2026, 9, 30)


def test_schedule_vigency_changes_only_future(app, system):
    with app.app_context():
        employee = db.session.get(Employee, system["ana"])
        before, _ = employee_history(employee, date(2026, 9, 29), date(2026, 9, 29))
        assign_schedule(employee, db.session.get(Schedule, system["short"]), date(2026, 10, 1))
        db.session.commit()
        rows, _ = employee_history(employee, date(2026, 9, 29), date(2026, 10, 1))
        assert before[0]["expected"] == rows[0]["expected"] == 8 * 3600
        assert rows[1]["expected"] == 8 * 3600 and rows[2]["expected"] == 5 * 3600
        assignments = list(
            db.session.scalars(
                select(EmployeeSchedule)
                .where(EmployeeSchedule.employee_id == employee.id)
                .order_by(EmployeeSchedule.valid_from)
            )
        )
        assert assignments[0].valid_until == date(2026, 9, 30)


def test_retroactive_or_overlapping_assignment_is_rejected(app, system):
    with app.app_context():
        employee = db.session.get(Employee, system["ana"])
        short = db.session.get(Schedule, system["short"])
        with pytest.raises(DomainError):
            assign_schedule(employee, short, date(2026, 9, 29))
        assign_schedule(employee, short, date(2026, 10, 1))
        db.session.commit()
        with pytest.raises(DomainError):
            assign_schedule(employee, short, date(2026, 10, 1))


def test_deactivation_and_reactivation_preserve_gap(app, client, login, system, clock):
    login("diretor")
    client.post(f"/employees/{system['ana']}/status", data={"action": "deactivate"})
    clock("2026-10-02T20:00:00")
    client.post(f"/employees/{system['ana']}/status", data={"action": "activate", "schedule_id": system["full"]})
    with app.app_context():
        employee = db.session.get(Employee, system["ana"])
        assert employee.active and employee.users[0].active
        rows, _ = employee_history(employee, date(2026, 9, 30), date(2026, 10, 2))
        assert rows[0]["expected"] == 8 * 3600 and rows[1]["expected"] is None and rows[2]["expected"] == 8 * 3600


def test_default_seed_is_idempotent_and_has_no_default_account(app, system):
    assert app.test_cli_runner().invoke(args=["seed"]).exit_code == 0
    with app.app_context():
        assert len(list(db.session.scalars(select(Schedule)))) == 3
        assert len(list(db.session.scalars(select(User)))) == 3


def test_retention_is_three_calendar_months_and_handles_short_months():
    assert retention_cutoff(datetime(2026, 9, 30, 12)) == datetime(2026, 6, 30, 12)
    assert retention_cutoff(datetime(2026, 5, 31, 12)) == datetime(2026, 2, 28, 12)


@pytest.mark.parametrize(
    "url",
    [
        "/employees/",
        "/employees/create",
        "/admin/users",
        "/admin/users/create",
        "/admin/schedules",
        "/admin/schedules/create",
        "/admin/holidays",
        "/audit/",
        "/corrections/",
        "/reports/",
    ],
)
def test_all_director_pages_render(url, client, login):
    login("diretor")
    assert client.get(url).status_code == 200


def test_all_employee_pages_render(client, login, system):
    login()
    for url in ["/dashboard/", "/attendance/", "/corrections/", "/corrections/new", "/password"]:
        assert client.get(url).status_code == 200


def test_user_creation_enforces_role_binding(app, client, login, system):
    login("diretor")
    response = client.post(
        "/admin/users/create",
        data={"username": "novousuario", "role": "FUNCIONARIO", "employee_id": 0, "password": "new-user-test-password"},
    )
    assert "Selecione um funcionário" in response.text
    with app.app_context():
        assert db.session.scalar(select(User.id).where(User.username == "novousuario")) is None
