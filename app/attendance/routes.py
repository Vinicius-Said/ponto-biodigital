from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.services.attendance import register_attendance
from app.services.history import date_range, employee_history, visible_employee
from app.services.permissions import require_employee
from app.services.validation import DomainError

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


@attendance_bp.get("/")
@login_required
def index():
    employee_id = request.args.get("employee_id", type=int)
    if current_user.role == "FUNCIONARIO":
        if employee_id is not None and employee_id != current_user.employee_id:
            abort(404)
        employee_id = current_user.employee_id
    if employee_id is None:
        return redirect(url_for("employees.index"))
    employee = visible_employee(employee_id, current_user)
    start, end, period = date_range()
    rows, totals = employee_history(employee, start, end)
    return render_template(
        "attendance/index.html", employee=employee, rows=rows, totals=totals, start=start, end=end, period=period
    )


@attendance_bp.post("/register")
@require_employee
def register():
    try:
        _, label = register_attendance(
            current_user.employee_id, request.form.get("type"), request.form.get("work_date"), request.remote_addr
        )
        db.session.commit()
        flash(f"{label} registrada pelo horário do servidor.", "success")
    except DomainError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("dashboard.index"))
