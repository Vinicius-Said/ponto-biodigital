from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, select
from app.extensions import db
from app.forms import HolidayForm, PasswordForm, ScheduleForm, UserForm
from app.models import Employee, Holiday, Schedule, SystemState, User
from app.services.audit import write_audit
from app.services.clock import today
from app.services.permissions import require_director
from app.services.schedules import lock_employee
from app.services.time_calculator import clock_minutes

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/users")
@require_director
def users():
    users = list(db.session.scalars(select(User).order_by(User.active.desc(), User.username)))
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@require_director
def create_user():
    form = UserForm()
    linked = select(User.employee_id).where(User.employee_id.is_not(None))
    form.employee_id.choices = [(0, "Sem vínculo")] + [
        (e.id, e.name)
        for e in db.session.scalars(
            select(Employee).where(Employee.active.is_(True), Employee.id.not_in(linked)).order_by(Employee.name)
        )
    ]
    if form.validate_on_submit():
        if db.session.scalar(select(User.id).where(User.username == form.username.data)):
            form.username.errors.append("Este usuário já existe.")
        elif form.role.data == "FUNCIONARIO" and not form.employee_id.data:
            form.employee_id.errors.append("Selecione um funcionário ativo sem acesso.")
        elif form.role.data == "DIRETORIA" and form.employee_id.data:
            form.employee_id.errors.append("O perfil Diretoria não possui vínculo de marcação de ponto.")
        else:
            if form.employee_id.data:
                employee = lock_employee(form.employee_id.data)
                if not employee.active:
                    abort(409)
            user = User(username=form.username.data, role=form.role.data, employee_id=form.employee_id.data or None)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()
            write_audit("CRIAR_USUARIO", "users", user.id, {"usuario": user.username, "perfil": user.role})
            db.session.commit()
            flash("Usuário criado.", "success")
            return redirect(url_for("admin.users"))
    return render_template(
        "form.html",
        title="Novo usuário",
        subtitle="Crie outro diretor ou vincule acesso a um funcionário sem usuário.",
        form=form,
    )


@admin_bp.post("/users/<int:user_id>/status")
@require_director
def user_status(user_id):
    db.session.scalar(select(SystemState).where(SystemState.id == 1).with_for_update())
    user = db.session.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    if not user:
        abort(404)
    action = request.form.get("action")
    if action not in ("activate", "deactivate"):
        abort(400)
    active = action == "activate"
    if not active and user.id == current_user.id:
        flash("Use outro diretor para desativar sua conta.", "error")
    elif (
        not active
        and user.role == "DIRETORIA"
        and db.session.scalar(select(func.count(User.id)).where(User.role == "DIRETORIA", User.active.is_(True))) <= 1
    ):
        flash("É necessário manter pelo menos um diretor ativo.", "error")
    elif active and user.employee and not user.employee.active:
        flash("Reative o funcionário antes de ativar seu acesso.", "error")
    else:
        user.active = active
        user.session_version += 1
        write_audit("ATIVAR_USUARIO" if active else "DESATIVAR_USUARIO", "users", user.id, {"usuario": user.username})
        db.session.commit()
        flash("Acesso atualizado.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/password", methods=["GET", "POST"])
@require_director
def reset_password(user_id):
    user = db.get_or_404(User, user_id)
    form = PasswordForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
        )
        user.set_password(form.password.data)
        write_audit("REDEFINIR_SENHA", "users", user.id, {"usuario": user.username})
        db.session.commit()
        flash("Senha redefinida e sessões anteriores revogadas.", "success")
        return redirect(url_for("admin.users"))
    return render_template("form.html", title="Redefinir senha", subtitle=f"Usuário: {user.username}", form=form)


@admin_bp.get("/schedules")
@require_director
def schedules():
    schedules = list(db.session.scalars(select(Schedule).order_by(Schedule.start_time)))
    return render_template("admin/schedules.html", schedules=schedules)


@admin_bp.route("/schedules/create", methods=["GET", "POST"])
@require_director
def create_schedule():
    form = ScheduleForm()
    if form.validate_on_submit():
        work_minutes = clock_minutes(form.end_time.data) - clock_minutes(form.start_time.data)
        saturday_minutes = clock_minutes(form.saturday_end.data) - clock_minutes(form.saturday_start.data)
        if work_minutes <= form.interval_minutes.data or saturday_minutes <= 0:
            flash(
                "A saída deve ocorrer após a entrada, com tempo de trabalho positivo. Jornadas que cruzam a meia-noite não fazem parte deste MVP.",
                "error",
            )
        elif db.session.scalar(select(Schedule.id).where(Schedule.name == form.name.data)):
            form.name.errors.append("Já existe uma jornada com este nome.")
        else:
            schedule = Schedule(
                name=form.name.data,
                start_time=form.start_time.data,
                end_time=form.end_time.data,
                interval_minutes=form.interval_minutes.data,
                saturday_start=form.saturday_start.data,
                saturday_end=form.saturday_end.data,
            )
            db.session.add(schedule)
            db.session.flush()
            write_audit("CRIAR_JORNADA", "schedules", schedule.id, {"nome": schedule.name})
            db.session.commit()
            flash("Jornada criada. Vincule-a ao funcionário com uma vigência.", "success")
            return redirect(url_for("admin.schedules"))
    return render_template(
        "form.html",
        title="Nova jornada",
        subtitle="Jornadas existentes são preservadas. Crie uma nova versão para mudar os horários.",
        form=form,
    )


@admin_bp.route("/holidays", methods=["GET", "POST"])
@require_director
def holidays():
    form = HolidayForm()
    if form.validate_on_submit():
        if db.session.scalar(select(Holiday.id).where(Holiday.day == form.day.data)):
            form.day.errors.append("Já existe um feriado nessa data.")
        else:
            holiday = Holiday(day=form.day.data, name=form.name.data)
            db.session.add(holiday)
            db.session.flush()
            write_audit(
                "CADASTRAR_FERIADO", "holidays", holiday.id, {"data": holiday.day.isoformat(), "nome": holiday.name}
            )
            db.session.commit()
            flash("Feriado cadastrado: a previsão dessa data passa a ser zero.", "success")
            return redirect(url_for("admin.holidays"))
    holidays = list(db.session.scalars(select(Holiday).order_by(Holiday.day.desc())))
    return render_template("admin/holidays.html", form=form, holidays=holidays)


@admin_bp.post("/holidays/<int:holiday_id>/remove")
@require_director
def remove_holiday(holiday_id):
    holiday = db.get_or_404(Holiday, holiday_id)
    if holiday.day < today():
        flash("Feriados passados são preservados. Não é permitido removê-los.", "error")
    else:
        write_audit("REMOVER_FERIADO", "holidays", holiday.id, {"data": holiday.day.isoformat(), "nome": holiday.name})
        db.session.delete(holiday)
        db.session.commit()
        flash("Feriado removido.", "success")
    return redirect(url_for("admin.holidays"))
