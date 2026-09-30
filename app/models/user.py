from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.services.clock import utc_now


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("role IN ('FUNCIONARIO', 'DIRETORIA')", name="valid_role"),
        db.CheckConstraint("role != 'FUNCIONARIO' OR employee_id IS NOT NULL", name="employee_required"),
    )
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), unique=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    session_version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    @property
    def is_active(self):
        return self.active and (self.role == "DIRETORIA" or (self.employee is not None and self.employee.active))

    def is_admin(self):
        return self.role == "DIRETORIA"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="scrypt")
        self.session_version = (self.session_version or 0) + 1

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
