from datetime import date, datetime
import pytest
from sqlalchemy import select
from app.extensions import db
from app.models import AuditLog, CorrectionRequest, TimeRecord
from app.services.audit import prune_logs
from app.services.clock import to_utc
from app.services.history import employee_history
from conftest import PASSWORD


def seed_day(app, employee_id, short=False):
    with app.app_context():
        times = (
            [("ENTRADA", 13, 0), ("SAIDA", 18, 0)]
            if short
            else [("ENTRADA", 8, 3), ("INTERVALO_SAIDA", 12, 0), ("INTERVALO_RETORNO", 13, 0), ("SAIDA", 17, 0)]
        )
        for kind, hour, minute in times:
            db.session.add(
                TimeRecord(
                    employee_id=employee_id,
                    work_date=date(2026, 9, 29),
                    type=kind,
                    recorded_at=to_utc(datetime(2026, 9, 29, hour, minute)),
                    ip_address="10.0.0.5",
                )
            )
        db.session.commit()


def request(client, kind="ENTRADA", stamp="08:00", day="2026-09-29", reason="Esqueci de registrar no horário correto."):
    return client.post(
        "/corrections/new",
        data={"work_date": day, "requested_type": kind, "requested_time": stamp, "reason": reason},
        follow_redirects=True,
    )


def admin_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "diretor", "password": PASSWORD})
    return client


def test_approval_preserves_original_timestamp_and_ip(app, client, login, system):
    seed_day(app, system["ana"])
    login()
    assert "Aguardando análise" in request(client).text
    with app.app_context():
        correction = db.session.scalar(select(CorrectionRequest))
        cid = correction.id
    admin = admin_client(app)
    assert (
        admin.post(
            f"/corrections/{cid}", data={"decision": "APROVADO", "reason": "Horário confirmado pela diretoria."}
        ).status_code
        == 302
    )
    with app.app_context():
        record = db.session.scalar(
            select(TimeRecord).where(TimeRecord.employee_id == system["ana"], TimeRecord.type == "ENTRADA")
        )
        assert record.recorded_at == datetime(2026, 9, 29, 11, 3) and record.corrected_at == datetime(2026, 9, 29, 11)
        assert record.ip_address == "10.0.0.5" and record.source == "SERVIDOR"
        correction = db.session.get(CorrectionRequest, cid)
        assert correction.previous_value == record.recorded_at and correction.status == "APROVADO"
        assert correction.reviewed_by == system["director"] and correction.reviewed_at is not None
        assert db.session.scalar(select(AuditLog).where(AuditLog.action == "APROVAR_CORRECAO"))
        rows, _ = employee_history(record.employee, date(2026, 9, 29), date(2026, 9, 29))
        assert rows[0]["worked"] == 8 * 3600 and rows[0]["difference"] == 0


def test_rejection_keeps_record_and_requires_reason(app, client, login, system):
    seed_day(app, system["ana"])
    login()
    request(client)
    with app.app_context():
        cid = db.session.scalar(select(CorrectionRequest.id))
    admin = admin_client(app)
    assert "motivo da recusa" in admin.post(f"/corrections/{cid}", data={"decision": "RECUSADO", "reason": ""}).text
    admin.post(f"/corrections/{cid}", data={"decision": "RECUSADO", "reason": "Horário não confirmado."})
    with app.app_context():
        correction = db.session.get(CorrectionRequest, cid)
        assert correction.status == "RECUSADO" and correction.time_record.corrected_at is None
        assert correction.review_reason == "Horário não confirmado."


def test_missing_punch_can_be_requested_and_added_without_fake_original(app, client, login, system):
    with app.app_context():
        db.session.add(
            TimeRecord(
                employee_id=system["bruno"],
                work_date=date(2026, 9, 29),
                type="ENTRADA",
                recorded_at=to_utc(datetime(2026, 9, 29, 13)),
            )
        )
        db.session.commit()
    login("bruno")
    request(client, "SAIDA", "18:00")
    with app.app_context():
        correction = db.session.scalar(select(CorrectionRequest))
        cid = correction.id
        assert correction.time_record_id is None and correction.previous_value is None
    admin_client(app).post(f"/corrections/{cid}", data={"decision": "APROVADO", "reason": "Confirmado."})
    with app.app_context():
        correction = db.session.get(CorrectionRequest, cid)
        assert correction.time_record.source == "CORRECAO" and correction.previous_value is None
        rows, _ = employee_history(correction.employee, date(2026, 9, 29), date(2026, 9, 29))
        assert rows[0]["complete"] and rows[0]["worked"] == 5 * 3600


def test_duplicate_pending_request_is_blocked(app, client, login, system):
    seed_day(app, system["ana"])
    login()
    request(client)
    assert "Já existe uma solicitação pendente" in request(client, stamp="08:01").text
    with app.app_context():
        assert len(list(db.session.scalars(select(CorrectionRequest)))) == 1


def test_employee_cannot_review_or_read_other_employees_correction(app, client, login, system):
    seed_day(app, system["ana"])
    login()
    request(client)
    with app.app_context():
        cid = db.session.scalar(select(CorrectionRequest.id))
    assert client.post(f"/corrections/{cid}", data={"decision": "APROVADO"}).status_code == 403
    login("bruno")
    assert client.get(f"/corrections/{cid}").status_code == 404


@pytest.mark.parametrize(
    "kind,stamp,day",
    [("ENTRADA", "12:01", "2026-09-29"), ("SAIDA", "18:00", "2026-10-01"), ("ENTRADA", "08:00", "2026-08-01")],
)
def test_invalid_correction_does_not_persist(app, client, login, system, kind, stamp, day):
    seed_day(app, system["ana"])
    login()
    request(client, kind, stamp, day)
    with app.app_context():
        assert db.session.scalar(select(CorrectionRequest.id)) is None


def test_short_schedule_rejects_interval_correction(app, client, login, system):
    login("bruno")
    assert "não possui intervalo" in request(client, "INTERVALO_SAIDA", "15:00").text


def test_request_cannot_be_reviewed_twice(app, client, login, system):
    seed_day(app, system["ana"])
    login()
    request(client)
    with app.app_context():
        cid = db.session.scalar(select(CorrectionRequest.id))
    admin = admin_client(app)
    admin.post(f"/corrections/{cid}", data={"decision": "APROVADO", "reason": "Confirmado."})
    assert (
        "já foi analisada"
        in admin.post(f"/corrections/{cid}", data={"decision": "RECUSADO", "reason": "Não confirmado."}).text
    )
    with app.app_context():
        assert db.session.get(CorrectionRequest, cid).status == "APROVADO"


def test_history_of_multiple_corrections_survives_log_pruning(app, client, login, system):
    seed_day(app, system["ana"])
    login()
    request(client)
    with app.app_context():
        cid = db.session.scalar(select(CorrectionRequest.id))
    admin = admin_client(app)
    admin.post(f"/corrections/{cid}", data={"decision": "APROVADO", "reason": "Confirmado."})
    request(client, stamp="08:01")
    with app.app_context():
        second = db.session.scalar(select(CorrectionRequest).order_by(CorrectionRequest.id.desc()))
        cid = second.id
    admin.post(f"/corrections/{cid}", data={"decision": "APROVADO", "reason": "Nova informação confirmada."})
    with app.app_context():
        for log in db.session.scalars(select(AuditLog)):
            log.created_at = datetime(2025, 1, 1)
        db.session.commit()
        prune_logs()
        assert not list(db.session.scalars(select(AuditLog)))
        revisions = list(db.session.scalars(select(CorrectionRequest).order_by(CorrectionRequest.id)))
        assert len(revisions) == 2 and revisions[0].previous_value == datetime(2026, 9, 29, 11, 3)
        assert revisions[1].previous_value == datetime(2026, 9, 29, 11)
        assert revisions[1].time_record.recorded_at == datetime(2026, 9, 29, 11, 3)
        assert revisions[1].time_record.effective_at == datetime(2026, 9, 29, 11, 1)


def test_director_direct_adjustment_is_audited(app, client, login, system):
    seed_day(app, system["ana"])
    login("diretor")
    response = client.post(
        f"/corrections/adjust/{system['ana']}",
        data={
            "work_date": "2026-09-29",
            "requested_type": "ENTRADA",
            "requested_time": "08:00",
            "reason": "Horário confirmado em conferência.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200 and "Decisão registrada" in response.text
    with app.app_context():
        correction = db.session.scalar(select(CorrectionRequest))
        assert correction.status == "APROVADO" and correction.reviewed_by == system["director"]
