from io import BytesIO
from flask import Blueprint, abort, render_template, request, send_file
from sqlalchemy import select
from app.extensions import db
from app.models import CorrectionRequest, Employee
from app.services.audit import write_audit
from app.services.history import date_range, employee_history
from app.services.permissions import require_director
from app.services.pdf_report import build_pdf

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def report_data():
    start, end, period = date_range()
    raw_id = request.args.get("employee_id", "0")
    try:
        employee_id = int(raw_id)
    except ValueError:
        abort(400)
    employees = list(db.session.scalars(select(Employee).order_by(Employee.name)))
    selected = [e for e in employees if e.id == employee_id] if employee_id else employees
    if employee_id and not selected:
        abort(404)
    reports = []
    for employee in selected:
        rows, totals = employee_history(employee, start, end)
        corrections = list(
            db.session.scalars(
                select(CorrectionRequest)
                .where(CorrectionRequest.employee_id == employee.id, CorrectionRequest.work_date.between(start, end))
                .order_by(CorrectionRequest.work_date, CorrectionRequest.created_at)
            )
        )
        reports.append({"employee": employee, "rows": rows, "totals": totals, "corrections": corrections})
    return employees, reports, start, end, period, employee_id


@reports_bp.get("/")
@require_director
def index():
    employees, reports, start, end, period, employee_id = report_data()
    return render_template(
        "reports/index.html",
        employees=employees,
        reports=reports,
        start=start,
        end=end,
        period=period,
        employee_id=employee_id,
    )


@reports_bp.get("/pdf")
@require_director
def pdf():
    _, reports, start, end, _, employee_id = report_data()
    payload = build_pdf(reports, start, end)
    write_audit(
        "GERAR_RELATORIO",
        "employees",
        employee_id or None,
        {"inicio": start.isoformat(), "fim": end.isoformat(), "formato": "PDF", "funcionarios": len(reports)},
    )
    db.session.commit()
    return send_file(
        BytesIO(payload),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"ponto-biodigital-{start.isoformat()}-{end.isoformat()}.pdf",
        max_age=0,
    )
