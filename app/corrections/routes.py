from datetime import date
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from app.extensions import db
from app.forms import CorrectionForm, ReviewForm
from app.models import CorrectionRequest, Employee
from app.services.corrections import request_correction, review_correction
from app.services.permissions import require_director, require_employee
from app.services.validation import DomainError

corrections_bp = Blueprint("corrections", __name__, url_prefix="/corrections")


@corrections_bp.get("/")
@login_required
def index():
    status = request.args.get("status", "PENDENTE")
    if status not in ("PENDENTE", "APROVADO", "RECUSADO", "TODOS"):
        abort(400)
    query = select(CorrectionRequest)
    if current_user.role == "FUNCIONARIO":
        query = query.where(CorrectionRequest.employee_id == current_user.employee_id)
    if status != "TODOS":
        query = query.where(CorrectionRequest.status == status)
    pagination = db.paginate(query.order_by(CorrectionRequest.created_at.desc()), per_page=20, max_per_page=20)
    return render_template("corrections/index.html", pagination=pagination, status=status)


@corrections_bp.route("/new", methods=["GET", "POST"])
@require_employee
def create():
    form = CorrectionForm()
    if request.method == "GET":
        try:
            if request.args.get("day"):
                form.work_date.data = date.fromisoformat(request.args["day"])
        except ValueError:
            abort(400)
        if request.args.get("type") in dict(form.requested_type.choices):
            form.requested_type.data = request.args["type"]
    if form.validate_on_submit():
        try:
            correction = request_correction(
                current_user.employee_id,
                form.work_date.data,
                form.requested_type.data,
                form.requested_time.data,
                form.reason.data,
            )
            db.session.commit()
            flash("Solicitação enviada à diretoria.", "success")
            return redirect(url_for("corrections.detail", correction_id=correction.id))
        except DomainError as error:
            db.session.rollback()
            flash(str(error), "error")
    return render_template(
        "form.html",
        title="Solicitar correção",
        subtitle="Ajuste um horário ou informe uma marcação esquecida. O motivo é obrigatório.",
        form=form,
    )


@corrections_bp.route("/adjust/<int:employee_id>", methods=["GET", "POST"])
@require_director
def adjust(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    form = CorrectionForm()
    if form.validate_on_submit():
        try:
            correction = request_correction(
                employee.id, form.work_date.data, form.requested_type.data, form.requested_time.data, form.reason.data
            )
            review_correction(
                correction.id,
                "APROVADO",
                "Ajuste realizado diretamente pela diretoria.",
                current_user.id,
                request.remote_addr,
            )
            db.session.commit()
            flash("Ajuste administrativo registrado com histórico preservado.", "success")
            return redirect(url_for("corrections.detail", correction_id=correction.id))
        except DomainError as error:
            db.session.rollback()
            flash(str(error), "error")
    return render_template(
        "form.html",
        title="Ajustar ponto",
        subtitle=f"{employee.name} · O ajuste será aplicado e ficará no histórico de correções.",
        form=form,
    )


@corrections_bp.route("/<int:correction_id>", methods=["GET", "POST"])
@login_required
def detail(correction_id):
    query = select(CorrectionRequest).where(CorrectionRequest.id == correction_id)
    if current_user.role == "FUNCIONARIO":
        query = query.where(CorrectionRequest.employee_id == current_user.employee_id)
    correction = db.session.scalar(query)
    if not correction:
        abort(404)
    form = ReviewForm()
    if request.method == "POST":
        if current_user.role != "DIRETORIA":
            abort(403)
        if form.validate_on_submit():
            try:
                review_correction(
                    correction.id, form.decision.data, form.reason.data, current_user.id, request.remote_addr
                )
                db.session.commit()
                flash("Decisão registrada.", "success")
                return redirect(url_for("corrections.detail", correction_id=correction.id))
            except DomainError as error:
                db.session.rollback()
                flash(str(error), "error")
    return render_template("corrections/detail.html", correction=correction, form=form)
