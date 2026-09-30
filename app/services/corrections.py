from datetime import datetime
from types import SimpleNamespace
from sqlalchemy import select
from app.extensions import db
from app.models import CorrectionRequest, Holiday, TimeRecord
from app.services.audit import write_audit
from app.services.clock import to_utc, today, utc_now
from app.services.schedules import assignments_for, lock_employee, schedule_on
from app.services.time_calculator import sequence_for, validate_records
from app.services.validation import DomainError


def correction_candidate(employee, day, record_type, requested_value):
    schedule = schedule_on(assignments_for(employee.id), day)
    if day < employee.hired_on or day > today() or not schedule:
        raise DomainError("A data precisa estar no período de controle com jornada vigente, até hoje.")
    if requested_value > utc_now():
        raise DomainError("Não é possível solicitar um horário futuro.")
    records = list(
        db.session.scalars(select(TimeRecord).where(TimeRecord.employee_id == employee.id, TimeRecord.work_date == day))
    )
    holidays = set(db.session.scalars(select(Holiday.day).where(Holiday.day == day)))
    sequence = sequence_for(schedule, day, holidays, records)
    if record_type not in sequence:
        raise DomainError("Essa jornada não possui intervalo nesta data.")
    current = next((r for r in records if r.type == record_type), None)
    candidate = [r for r in records if r.type != record_type]
    candidate.append(SimpleNamespace(type=record_type, effective_at=requested_value))
    validate_records(candidate, sequence, day)
    return current


def request_correction(employee_id, day, record_type, requested_time, reason):
    employee = lock_employee(employee_id)
    requested_value = to_utc(datetime.combine(day, requested_time))
    record = correction_candidate(employee, day, record_type, requested_value)
    if record and record.effective_at == requested_value:
        raise DomainError("O horário solicitado já é o horário vigente.")
    pending = db.session.scalar(
        select(CorrectionRequest).where(
            CorrectionRequest.employee_id == employee.id,
            CorrectionRequest.work_date == day,
            CorrectionRequest.requested_type == record_type,
            CorrectionRequest.status == "PENDENTE",
        )
    )
    if pending:
        raise DomainError("Já existe uma solicitação pendente para essa marcação.")
    correction = CorrectionRequest(
        employee_id=employee.id,
        time_record_id=record.id if record else None,
        work_date=day,
        requested_type=record_type,
        previous_value=record.effective_at if record else None,
        requested_value=requested_value,
        reason=reason,
    )
    db.session.add(correction)
    db.session.flush()
    write_audit(
        "SOLICITAR_CORRECAO",
        "correction_requests",
        correction.id,
        {"tipo": record_type, "data": day.isoformat(), "motivo": reason},
    )
    return correction


def review_correction(correction_id, decision, reason, reviewer_id, ip_address):
    # Lock the employee first, consistently with punches and all requests.
    initial = db.session.get(CorrectionRequest, correction_id)
    if not initial:
        raise DomainError("Solicitação não encontrada.")
    employee = lock_employee(initial.employee_id)
    correction = db.session.scalar(
        select(CorrectionRequest)
        .where(CorrectionRequest.id == correction_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if correction.status != "PENDENTE":
        raise DomainError("Essa solicitação já foi analisada.")
    if decision not in ("APROVADO", "RECUSADO"):
        raise DomainError("Decisão inválida.")
    if decision == "RECUSADO" and len(reason.strip()) < 5:
        raise DomainError("Informe o motivo da recusa.")
    if decision == "APROVADO":
        record = correction_candidate(
            employee, correction.work_date, correction.requested_type, correction.requested_value
        )
        if (record.effective_at if record else None) != correction.previous_value:
            raise DomainError("O registro mudou após a solicitação. Recuse esta solicitação e peça uma nova correção.")
        if record:
            record.corrected_at = correction.requested_value
        else:
            record = TimeRecord(
                employee_id=employee.id,
                work_date=correction.work_date,
                type=correction.requested_type,
                recorded_at=correction.requested_value,
                source="CORRECAO",
                ip_address=ip_address,
            )
            db.session.add(record)
            db.session.flush()
            correction.time_record_id = record.id
    correction.status = decision
    correction.reviewed_by = reviewer_id
    correction.reviewed_at = utc_now()
    correction.review_reason = reason.strip()
    write_audit(
        "APROVAR_CORRECAO" if decision == "APROVADO" else "RECUSAR_CORRECAO",
        "correction_requests",
        correction.id,
        {
            "registro": correction.time_record_id,
            "anterior": correction.previous_value.isoformat() if correction.previous_value else None,
            "novo": correction.requested_value.isoformat(),
            "motivo": correction.reason,
            "justificativa": correction.review_reason,
        },
    )
    return correction
