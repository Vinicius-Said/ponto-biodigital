import re
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SelectField,
    DateField,
    TimeField,
    TextAreaField,
    IntegerField,
    SubmitField,
)
from wtforms.validators import DataRequired, Length, EqualTo, NumberRange, ValidationError
from app.services.clock import today


def username_validator(form, field):
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,79}", field.data or ""):
        raise ValidationError("Use 3 a 80 caracteres: letras minúsculas, números, ponto, hífen ou sublinhado.")


def username_field():
    return StringField(
        "Usuário", filters=[lambda x: (x or "").strip().lower()], validators=[DataRequired(), username_validator]
    )


def password_field(label="Senha inicial"):
    return PasswordField(
        label, validators=[DataRequired(), Length(min=10, max=128, message="Use entre 10 e 128 caracteres.")]
    )


class LoginForm(FlaskForm):
    username = StringField(
        "Usuário", filters=[lambda x: (x or "").strip().lower()], validators=[DataRequired(), Length(max=80)]
    )
    password = PasswordField("Senha", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("Entrar")


class SetupForm(FlaskForm):
    token = PasswordField("Token de configuração", validators=[DataRequired(), Length(max=128)])
    username = username_field()
    password = password_field("Senha")
    confirm = PasswordField(
        "Confirmar senha", validators=[DataRequired(), EqualTo("password", message="As senhas precisam ser iguais.")]
    )
    submit = SubmitField("Criar primeiro diretor")


class EmployeeForm(FlaskForm):
    name = StringField(
        "Nome completo", filters=[lambda x: (x or "").strip()], validators=[DataRequired(), Length(min=2, max=120)]
    )
    hired_on = DateField("Início do controle de ponto", default=today, validators=[DataRequired()])
    schedule_id = SelectField("Jornada", coerce=int, validators=[DataRequired()])
    username = username_field()
    password = password_field()
    submit = SubmitField("Cadastrar funcionário")


class NameForm(FlaskForm):
    name = StringField(
        "Nome completo", filters=[lambda x: (x or "").strip()], validators=[DataRequired(), Length(min=2, max=120)]
    )
    submit = SubmitField("Salvar nome")


class AssignmentForm(FlaskForm):
    schedule_id = SelectField("Nova jornada", coerce=int, validators=[DataRequired()])
    valid_from = DateField("Vigência a partir de", default=today, validators=[DataRequired()])
    submit = SubmitField("Vincular jornada")


class ScheduleForm(FlaskForm):
    name = StringField(
        "Nome da jornada", filters=[lambda x: (x or "").strip()], validators=[DataRequired(), Length(min=2, max=80)]
    )
    start_time = TimeField("Entrada (segunda a sexta)", validators=[DataRequired()])
    end_time = TimeField("Saída (segunda a sexta)", validators=[DataRequired()])
    interval_minutes = IntegerField("Intervalo em minutos", default=60, validators=[NumberRange(min=0, max=240)])
    saturday_start = TimeField("Entrada no sábado", validators=[DataRequired()])
    saturday_end = TimeField("Saída no sábado", validators=[DataRequired()])
    submit = SubmitField("Criar jornada")


class HolidayForm(FlaskForm):
    day = DateField("Data", validators=[DataRequired()])
    name = StringField(
        "Nome do feriado", filters=[lambda x: (x or "").strip()], validators=[DataRequired(), Length(min=2, max=120)]
    )
    submit = SubmitField("Cadastrar feriado")


class UserForm(FlaskForm):
    username = username_field()
    role = SelectField(
        "Perfil", choices=[("DIRETORIA", "Diretoria"), ("FUNCIONARIO", "Funcionário")], validators=[DataRequired()]
    )
    employee_id = SelectField("Funcionário (para perfil Funcionário)", coerce=int, choices=[(0, "Sem vínculo")])
    password = password_field()
    submit = SubmitField("Criar usuário")


class PasswordForm(FlaskForm):
    password = password_field("Nova senha")
    confirm = PasswordField(
        "Confirmar senha", validators=[DataRequired(), EqualTo("password", message="As senhas precisam ser iguais.")]
    )
    submit = SubmitField("Redefinir senha")


class OwnPasswordForm(PasswordForm):
    current_password = PasswordField("Senha atual", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("Alterar minha senha")


class CorrectionForm(FlaskForm):
    work_date = DateField("Data da marcação", default=today, validators=[DataRequired()])
    requested_type = SelectField(
        "Marcação",
        choices=[
            ("ENTRADA", "Entrada"),
            ("INTERVALO_SAIDA", "Saída para intervalo"),
            ("INTERVALO_RETORNO", "Retorno do intervalo"),
            ("SAIDA", "Saída"),
        ],
        validators=[DataRequired()],
    )
    requested_time = TimeField("Horário solicitado", format="%H:%M", validators=[DataRequired()])
    reason = TextAreaField(
        "Motivo", filters=[lambda x: (x or "").strip()], validators=[DataRequired(), Length(min=5, max=1000)]
    )
    submit = SubmitField("Enviar solicitação")


class ReviewForm(FlaskForm):
    decision = SelectField(
        "Decisão", choices=[("APROVADO", "Aprovar"), ("RECUSADO", "Recusar")], validators=[DataRequired()]
    )
    reason = TextAreaField(
        "Justificativa da decisão", filters=[lambda x: (x or "").strip()], validators=[Length(max=1000)]
    )
    submit = SubmitField("Confirmar decisão")

    def validate_reason(self, field):
        if self.decision.data == "RECUSADO" and len(field.data or "") < 5:
            raise ValidationError("Informe o motivo da recusa (mínimo de 5 caracteres).")
