from datetime import time, timedelta
from sqlalchemy import select
from app.extensions import db
from app.models import Employee, EmployeeSchedule, Schedule
from app.services.clock import today
from app.services.validation import DomainError


def seed_schedules():
    for start, end, interval in [(8, 17, 60), (9, 18, 60), (13, 18, 0)]:
        name = f"{start:02d}:00–{end:02d}:00"
        if not db.session.scalar(select(Schedule).where(Schedule.name == name)):
            db.session.add(
                Schedule(
                    name=name,
                    start_time=time(start),
                    end_time=time(end),
                    interval_minutes=interval,
                    saturday_start=time(9),
                    saturday_end=time(13),
                )
            )
    db.session.flush()


def assignments_for(employee_id):
    return list(
        db.session.scalars(
            select(EmployeeSchedule)
            .where(EmployeeSchedule.employee_id == employee_id, EmployeeSchedule.cancelled.is_(False))
            .order_by(EmployeeSchedule.valid_from)
        )
    )


def schedule_on(assignments, day):
    for assignment in reversed(assignments):
        if (
            not assignment.cancelled
            and assignment.valid_from <= day
            and (assignment.valid_until is None or day <= assignment.valid_until)
        ):
            return assignment.schedule
    return None


def assign_schedule(employee, schedule, valid_from):
    """Forward-only append. Referenced Schedule rows have no editing endpoint."""
    if not employee.active:
        raise DomainError("Reative o funcionário antes de vincular uma jornada.")
    if valid_from < today() or valid_from < employee.hired_on:
        raise DomainError("A nova vigência deve começar hoje ou no futuro, após o início do controle.")
    assignments = assignments_for(employee.id)
    if assignments and valid_from <= assignments[-1].valid_from:
        raise DomainError(
            "A nova vigência deve ser posterior à última jornada cadastrada. Para nova alteração no mesmo dia, use o dia seguinte."
        )
    if assignments:
        assignments[-1].valid_until = valid_from - timedelta(days=1)
    assignment = EmployeeSchedule(employee_id=employee.id, schedule_id=schedule.id, valid_from=valid_from)
    db.session.add(assignment)
    return assignment


def lock_employee(employee_id):
    employee = db.session.scalar(
        select(Employee).where(Employee.id == employee_id).with_for_update().execution_options(populate_existing=True)
    )
    if employee is None:
        raise DomainError("Funcionário não encontrado.")
    return employee


def deactivate_employee(employee):
    day = today()
    assignments = assignments_for(employee.id)
    for assignment in assignments:
        if assignment.valid_from > day:
            assignment.cancelled = True
        elif assignment.valid_until is None or assignment.valid_until > day:
            assignment.valid_until = day
    employee.active = False
    for user in employee.users:
        user.active = False
        user.session_version += 1


def reactivate_employee(employee, schedule):
    day = max(today(), employee.hired_on)
    assignments = assignments_for(employee.id)
    existing = db.session.scalar(
        select(EmployeeSchedule).where(EmployeeSchedule.employee_id == employee.id, EmployeeSchedule.valid_from == day)
    )
    if existing:
        if existing.schedule_id != schedule.id:
            raise DomainError(
                "Já existe outra jornada com início nesta data. Reative com essa jornada e altere a vigência no dia seguinte."
            )
        existing.cancelled = False
        existing.valid_until = None
    else:
        if assignments and (assignments[-1].valid_until is None or assignments[-1].valid_until >= day):
            assignments[-1].valid_until = day - timedelta(days=1)
        db.session.add(EmployeeSchedule(employee_id=employee.id, schedule_id=schedule.id, valid_from=day))
    employee.active = True
    for user in employee.users:
        user.active = True
        user.session_version += 1
