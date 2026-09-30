from flask import render_template
from flask_login import current_user, login_required
from sqlalchemy import func, select
from app.extensions import db
from app.models import CorrectionRequest, Employee
from app.services.clock import local_time, today, utc_now
from app.services.history import employee_history
from . import dashboard_bp


@dashboard_bp.get("/")
@login_required
def index():
    day = today()
    if current_user.role == "DIRETORIA":
        employees = list(db.session.scalars(select(Employee).where(Employee.active.is_(True)).order_by(Employee.name)))
        statuses = []
        for employee in employees:
            rows, _ = employee_history(employee, day, day, live=True)
            statuses.append((employee, rows[0] if rows else None))
        pending = db.session.scalar(
            select(func.count(CorrectionRequest.id)).where(CorrectionRequest.status == "PENDENTE")
        )
        recorded = sum(bool(row and row["records"]) for _, row in statuses)
        return render_template("dashboard/director.html", statuses=statuses, pending=pending, recorded=recorded)
    rows, _ = employee_history(current_user.employee, day, day, live=True)
    recent, totals = employee_history(current_user.employee, day.replace(day=1), day)
    pending = db.session.scalar(
        select(func.count(CorrectionRequest.id)).where(
            CorrectionRequest.employee_id == current_user.employee_id, CorrectionRequest.status == "PENDENTE"
        )
    )
    return render_template(
        "dashboard/employee.html",
        row=rows[0] if rows else None,
        recent=list(reversed(recent))[:5],
        totals=totals,
        pending=pending,
        now_iso=utc_now().isoformat() + "Z",
        now_label=local_time(utc_now()).strftime("%H:%M:%S"),
    )
