from pathlib import Path
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, select
from app.extensions import db
from app.models import SystemState


def test_pdf_individual_and_consolidated_and_report_audit(app, client, login, system, tmp_path):
    login("diretor")
    response = client.get(f"/reports/pdf?employee_id={system['ana']}&period=month")
    assert response.status_code == 200 and response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-") and len(response.data) > 2000
    assert "attachment" in response.headers["Content-Disposition"]
    consolidated = client.get("/reports/pdf?employee_id=0&period=month")
    assert consolidated.status_code == 200 and consolidated.data.startswith(b"%PDF-")
    with app.app_context():
        from app.models import AuditLog

        log = db.session.scalar(
            select(AuditLog).where(AuditLog.action == "GERAR_RELATORIO").order_by(AuditLog.id.desc())
        )
        assert log.details["funcionarios"] == 2


def test_pdf_handles_long_untrusted_text_and_corrections(app, client, login, system):
    from test_corrections import seed_day

    seed_day(app, system["ana"])
    login("diretor")
    client.post(
        f"/corrections/adjust/{system['ana']}",
        data={
            "work_date": "2026-09-29",
            "requested_type": "ENTRADA",
            "requested_time": "08:00",
            "reason": ("Texto de teste & <tag> " * 35),
        },
    )
    response = client.get(f"/reports/pdf?employee_id={system['ana']}&period=month")
    assert response.status_code == 200 and response.data.startswith(b"%PDF-")


def test_migration_round_trip_is_real_and_inserts_bootstrap_state(app):
    root = Path(__file__).resolve().parent.parent
    with app.app_context():
        assert db.session.get(SystemState, 1).setup_completed is False
        db.session.remove()
        downgrade(directory=str(root / "migrations"), revision="base")
        assert "users" not in inspect(db.engine).get_table_names()
        upgrade(directory=str(root / "migrations"))
        assert db.session.get(SystemState, 1).setup_completed is False
        assert set(["users", "employee_schedules", "correction_requests", "time_records"]).issubset(
            inspect(db.engine).get_table_names()
        )
