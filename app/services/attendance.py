from sqlalchemy import select
from app.extensions import db
from app.models import Holiday, TimeRecord
from app.models.time_record import RECORD_LABELS
from app.services.audit import write_audit
from app.services.clock import local_time, utc_now
from app.services.schedules import assignments_for, lock_employee, schedule_on
from app.services.time_calculator import daily_summary
from app.services.validation import DomainError


def register_attendance(employee_id, expected_type, expected_day, ip_address):
    employee = lock_employee(employee_id)
    if not employee.active:
        raise DomainError("Funcionário inativo.")
    now = utc_now()
    day = local_time(now).date()
    if expected_day != day.isoformat():
        raise DomainError("A data mudou. Atualize a página antes de registrar.")
    schedule = schedule_on(assignments_for(employee.id), day)
    if not schedule:
        raise DomainError("Você não possui jornada vigente para hoje. Contate a diretoria.")
    records = list(
        db.session.scalars(select(TimeRecord).where(TimeRecord.employee_id == employee.id, TimeRecord.work_date == day))
    )
    holidays = set(db.session.scalars(select(Holiday.day).where(Holiday.day == day)))
    summary = daily_summary(day, schedule, records, holidays, day)
    record_type = summary["next_type"]
    if not record_type:
        raise DomainError("As marcações do dia já foram concluídas ou precisam de correção.")
    if expected_type != record_type:
        raise DomainError("O ponto já mudou. Atualize a página para verificar a próxima marcação.")
    if records and now <= max(record.effective_at for record in records):
        raise DomainError("Aguarde o relógio do servidor avançar antes de registrar novamente.")
    record = TimeRecord(
        employee_id=employee.id, type=record_type, work_date=day, recorded_at=now, ip_address=ip_address
    )
    db.session.add(record)
    db.session.flush()
    write_audit(
        "REGISTRAR_PONTO",
        "time_records",
        record.id,
        {"tipo": record_type, "horario": now.isoformat(), "origem": "SERVIDOR"},
    )
    return record, RECORD_LABELS[record_type]
