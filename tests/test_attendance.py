from datetime import date, datetime
import pytest
from sqlalchemy import select
from app.extensions import db
from app.models import Holiday, TimeRecord
from app.services.clock import to_utc
from app.services.history import employee_history
from app.services.time_calculator import format_duration


def punch(client, kind, day="2026-09-30"):
    return client.post("/attendance/register", data={"type": kind, "work_date": day}, follow_redirects=True)


def test_full_day_sequence_uses_server_time_and_ip(app, client, login, system, clock):
    login()
    for stamp, kind in [
        ("11:00:00", "ENTRADA"),
        ("15:00:00", "INTERVALO_SAIDA"),
        ("16:00:00", "INTERVALO_RETORNO"),
        ("20:00:00", "SAIDA"),
    ]:
        clock(f"2026-09-30T{stamp}")
        response = client.post(
            "/attendance/register",
            data={
                "type": kind,
                "work_date": "2026-09-30",
                "recorded_at": "1999-01-01T00:00",
                "employee_id": system["bruno"],
            },
            environ_overrides={"REMOTE_ADDR": "10.0.0.9", "HTTP_X_FORWARDED_FOR": "6.6.6.6"},
        )
        assert response.status_code == 302
    with app.app_context():
        records = list(db.session.scalars(select(TimeRecord)))
        assert len(records) == 4 and all(r.employee_id == system["ana"] for r in records)
        assert all(r.ip_address == "10.0.0.9" for r in records)
        assert records[0].recorded_at == datetime(2026, 9, 30, 11)
        employee = records[0].employee
        rows, totals = employee_history(employee, date(2026, 9, 30), date(2026, 9, 30))
        assert rows[0]["complete"] and rows[0]["worked"] == 8 * 3600 and rows[0]["difference"] == 0
        assert totals["difference"] == 0


def test_duplicate_and_out_of_order_punches_do_not_advance_day(app, client, login, system, clock):
    clock("2026-09-30T11:00:00")
    login()
    assert "O ponto já mudou" in punch(client, "SAIDA").text
    punch(client, "ENTRADA")
    clock("2026-09-30T11:01:00")
    assert "O ponto já mudou" in punch(client, "ENTRADA").text
    with app.app_context():
        assert len(list(db.session.scalars(select(TimeRecord)))) == 1


def test_short_schedule_has_two_punches(app, client, login, clock, system):
    login("bruno")
    clock("2026-09-30T16:00:00")
    punch(client, "ENTRADA")
    clock("2026-09-30T21:00:00")
    punch(client, "SAIDA")
    with app.app_context():
        from app.models import Employee

        rows, _ = employee_history(db.session.get(Employee, system["bruno"]), date(2026, 9, 30), date(2026, 9, 30))
        assert rows[0]["complete"] and rows[0]["worked"] == 5 * 3600 and rows[0]["expected"] == 5 * 3600


@pytest.mark.parametrize(
    "day,start,end,expected",
    [("2026-10-03", "12:00:00", "16:00:00", 4 * 3600), ("2026-10-04", "12:00:00", "16:00:00", 0)],
)
def test_saturday_and_sunday(app, client, login, system, clock, day, start, end, expected):
    clock(f"{day}T{start}")
    login()
    punch(client, "ENTRADA", day)
    clock(f"{day}T{end}")
    punch(client, "SAIDA", day)
    with app.app_context():
        from app.models import Employee

        d = date.fromisoformat(day)
        rows, _ = employee_history(db.session.get(Employee, system["ana"]), d, d)
        assert rows[0]["expected"] == expected and rows[0]["worked"] == 4 * 3600
        assert rows[0]["difference"] == 4 * 3600 - expected


def test_registered_holiday_is_day_off(app, system):
    with app.app_context():
        from app.models import Employee

        db.session.add(Holiday(day=date(2026, 9, 29), name="Feriado de teste"))
        db.session.commit()
        rows, _ = employee_history(db.session.get(Employee, system["ana"]), date(2026, 9, 29), date(2026, 9, 29))
        assert rows[0]["expected"] == 0 and rows[0]["difference"] == 0 and rows[0]["status"] == "Folga"


def test_incomplete_past_day_does_not_falsify_balance(app, system):
    with app.app_context():
        db.session.add(
            TimeRecord(
                employee_id=system["ana"],
                work_date=date(2026, 9, 29),
                type="ENTRADA",
                recorded_at=to_utc(datetime(2026, 9, 29, 8)),
                source="SERVIDOR",
            )
        )
        db.session.commit()
        from app.models import Employee

        rows, totals = employee_history(db.session.get(Employee, system["ana"]), date(2026, 9, 29), date(2026, 9, 29))
        assert rows[0]["status"] == "Incompleto" and rows[0]["difference"] is None
        assert totals["difference"] == 0 and totals["pending_days"] == 1


def test_absence_is_negative_only_after_date_passes(app, system):
    with app.app_context():
        from app.models import Employee

        employee = db.session.get(Employee, system["ana"])
        rows, _ = employee_history(employee, date(2026, 9, 29), date(2026, 9, 30))
        assert rows[0]["difference"] == -8 * 3600 and rows[1]["difference"] is None
        assert format_duration(-65 * 60) == "−01:05"


def test_midnight_utc_still_belongs_to_previous_brazil_date(app, client, login, clock, system):
    clock("2026-10-01T01:00:00")
    login()
    punch(client, "ENTRADA", "2026-09-30")
    with app.app_context():
        record = db.session.scalar(select(TimeRecord))
        assert record.work_date == date(2026, 9, 30) and record.recorded_at == datetime(2026, 10, 1, 1)


def test_stale_date_requires_page_refresh(client, login, clock):
    clock("2026-10-01T04:00:00")
    login()
    assert "A data mudou" in punch(client, "ENTRADA", "2026-09-30").text


def test_director_cannot_punch(client, login):
    login("diretor")
    assert client.post("/attendance/register", data={"type": "ENTRADA", "work_date": "2026-09-30"}).status_code == 403


@pytest.mark.parametrize(
    "query",
    [
        "period=bad",
        "period=custom&start=x&end=y",
        "period=custom&start=2026-10-01&end=2026-01-01",
        "period=custom&start=2024-01-01&end=2026-01-01",
    ],
)
def test_history_filters_validate_dates(query, client, login):
    login()
    assert client.get("/attendance/?" + query).status_code == 400
