from collections import defaultdict
from datetime import date, timedelta
from flask import abort, request
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.extensions import db
from app.models import Employee, EmployeeSchedule, Holiday, TimeRecord
from app.services.clock import today
from app.services.time_calculator import daily_summary


def date_range():
    current = today()
    period = request.args.get("period", "month")
    if period == "day":
        start = end = current
    elif period == "week":
        start, end = current - timedelta(days=current.weekday()), current
    elif period == "month":
        start, end = current.replace(day=1), current
    elif period == "custom":
        try:
            start, end = (
                date.fromisoformat(request.args.get("start", "")),
                date.fromisoformat(request.args.get("end", "")),
            )
        except ValueError:
            abort(400, description="Informe datas válidas para o período personalizado.")
    else:
        abort(400, description="Período inválido.")
    if start > end or (end - start).days > 365:
        abort(400, description="O período deve ter até 366 dias e a data inicial não pode ser maior que a final.")
    return start, end, period


def employee_history(employee, start, end, live=False):
    assignments = list(
        db.session.scalars(
            select(EmployeeSchedule)
            .options(selectinload(EmployeeSchedule.schedule))
            .where(EmployeeSchedule.employee_id == employee.id, EmployeeSchedule.cancelled.is_(False))
            .order_by(EmployeeSchedule.valid_from)
        )
    )
    holidays = set(db.session.scalars(select(Holiday.day).where(Holiday.day.between(start, end))))
    records = list(
        db.session.scalars(
            select(TimeRecord)
            .where(TimeRecord.employee_id == employee.id, TimeRecord.work_date.between(start, end))
            .order_by(TimeRecord.work_date, TimeRecord.recorded_at)
        )
    )
    grouped = defaultdict(list)
    for record in records:
        grouped[record.work_date].append(record)
    from app.services.schedules import schedule_on

    current_day = today()
    rows, day = [], max(start, employee.hired_on)
    while day <= end:
        rows.append(daily_summary(day, schedule_on(assignments, day), grouped[day], holidays, current_day, live=live))
        day += timedelta(days=1)
    settled = [row for row in rows if row["difference"] is not None]
    totals = {
        "worked": sum(row["worked"] for row in rows),
        "expected": sum(row["expected"] or 0 for row in rows),
        "difference": sum(row["difference"] for row in settled),
        "pending_days": sum(row["difference"] is None and row["expected"] is not None for row in rows),
        "incomplete_days": sum(row["status"] in ("Incompleto", "Inconsistente") for row in rows),
    }
    return rows, totals


def visible_employee(employee_id, user):
    if user.role == "FUNCIONARIO" and employee_id != user.employee_id:
        abort(404)
    employee = db.session.get(Employee, employee_id)
    if not employee:
        abort(404)
    return employee
