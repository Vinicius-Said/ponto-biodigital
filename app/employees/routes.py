from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from app.extensions import db
from app.forms import AssignmentForm, EmployeeForm, NameForm
from app.models import Employee, EmployeeSchedule, Schedule, User
from app.services.audit import write_audit
from app.services.clock import today
from app.services.history import employee_history
from app.services.permissions import require_director
from app.services.schedules import assign_schedule, deactivate_employee, lock_employee, reactivate_employee
from app.services.validation import DomainError

employees_bp = Blueprint("employees", __name__, url_prefix="/employees")


def schedules_choices():
    return [
        (s.id, f"{s.name} · intervalo {s.interval_minutes} min")
        for s in db.session.scalars(select(Schedule).order_by(Schedule.start_time))
    ]


@employees_bp.get("/")
@require_director
def index():
    employees = list(db.session.scalars(select(Employee).order_by(Employee.active.desc(), Employee.name)))
    return render_template("employees/index.html", employees=employees)


@employees_bp.route("/create", methods=["GET", "POST"])
@require_director
def create():
    form = EmployeeForm()
    form.schedule_id.choices = schedules_choices()
    if form.validate_on_submit():
        if form.hired_on.data > today():
            form.hired_on.errors.append("Para cadastrar agora, informe uma data até hoje.")
        elif db.session.scalar(select(User.id).where(User.username == form.username.data)):
            form.username.errors.append("Este usuário já existe.")
        else:
            employee = Employee(name=form.name.data, hired_on=form.hired_on.data)
            db.session.add(employee)
            db.session.flush()
            user = User(username=form.username.data, role="FUNCIONARIO", employee_id=employee.id)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.add(
                EmployeeSchedule(
                    employee_id=employee.id, schedule_id=form.schedule_id.data, valid_from=employee.hired_on
                )
            )
            db.session.flush()
            write_audit(
                "CADASTRAR_FUNCIONARIO",
                "employees",
                employee.id,
                {"nome": employee.name, "inicio": employee.hired_on.isoformat()},
            )
            write_audit("CRIAR_USUARIO", "users", user.id, {"usuario": user.username, "perfil": user.role})
            db.session.commit()
            flash("Funcionário e acesso cadastrados. Entregue a senha inicial por um canal privado.", "success")
            return redirect(url_for("employees.detail", employee_id=employee.id))
    return render_template(
        "form.html",
        title="Novo funcionário",
        subtitle="Cadastre a pessoa, a jornada e o acesso em uma única etapa.",
        form=form,
    )


@employees_bp.get("/<int:employee_id>")
@require_director
def detail(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    assignment_form = AssignmentForm()
    assignment_form.schedule_id.choices = schedules_choices()
    rows, _ = employee_history(employee, today(), today())
    return render_template(
        "employees/detail.html", employee=employee, form=assignment_form, row=rows[0] if rows else None
    )


@employees_bp.route("/<int:employee_id>/edit", methods=["GET", "POST"])
@require_director
def edit(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    form = NameForm(obj=employee)
    if form.validate_on_submit():
        employee = lock_employee(employee.id)
        old = employee.name
        employee.name = form.name.data
        write_audit("ALTERAR_FUNCIONARIO", "employees", employee.id, {"anterior": old, "novo": employee.name})
        db.session.commit()
        flash("Nome atualizado.", "success")
        return redirect(url_for("employees.detail", employee_id=employee.id))
    return render_template("form.html", title="Editar funcionário", subtitle=employee.name, form=form)


@employees_bp.post("/<int:employee_id>/schedule")
@require_director
def change_schedule(employee_id):
    form = AssignmentForm()
    form.schedule_id.choices = schedules_choices()
    if not form.validate_on_submit():
        flash("Verifique a jornada e a data de vigência.", "error")
        return redirect(url_for("employees.detail", employee_id=employee_id))
    try:
        employee = lock_employee(employee_id)
        schedule = db.get_or_404(Schedule, form.schedule_id.data)
        assignment = assign_schedule(employee, schedule, form.valid_from.data)
        db.session.flush()
        write_audit(
            "ALTERAR_JORNADA",
            "employee_schedules",
            assignment.id,
            {"funcionario": employee.id, "jornada": schedule.name, "vigencia": form.valid_from.data.isoformat()},
        )
        db.session.commit()
        flash("Nova jornada vinculada. O histórico anterior foi preservado.", "success")
    except DomainError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("employees.detail", employee_id=employee_id))


@employees_bp.post("/<int:employee_id>/status")
@require_director
def status(employee_id):
    action = request.form.get("action")
    if action not in ("activate", "deactivate"):
        abort(400)
    try:
        employee = lock_employee(employee_id)
        if action == "deactivate":
            if not employee.active:
                raise DomainError("O funcionário já está inativo.")
            deactivate_employee(employee)
        else:
            if employee.active:
                raise DomainError("O funcionário já está ativo.")
            schedule_id = request.form.get("schedule_id", type=int)
            schedule = db.session.get(Schedule, schedule_id) if schedule_id else None
            if not schedule:
                raise DomainError("Selecione uma jornada para reativar.")
            reactivate_employee(employee, schedule)
        write_audit(
            "REATIVAR_FUNCIONARIO" if employee.active else "DESATIVAR_FUNCIONARIO",
            "employees",
            employee.id,
            {"nome": employee.name, "responsavel": current_user.id},
        )
        db.session.commit()
        flash("Status atualizado. O histórico continua disponível.", "success")
    except DomainError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("employees.detail", employee_id=employee_id))
