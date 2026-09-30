from app.extensions import db
from app.services.clock import utc_now


class CorrectionRequest(db.Model):
    __tablename__ = "correction_requests"
    __table_args__ = (
        db.CheckConstraint("status IN ('PENDENTE', 'APROVADO', 'RECUSADO')", name="valid_status"),
        db.CheckConstraint(
            "requested_type IN ('ENTRADA', 'INTERVALO_SAIDA', 'INTERVALO_RETORNO', 'SAIDA')", name="valid_type"
        ),
        db.Index("ix_corrections_employee_date", "employee_id", "work_date"),
    )
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    time_record_id = db.Column(db.Integer, db.ForeignKey("time_records.id"))
    work_date = db.Column(db.Date, nullable=False)
    requested_type = db.Column(db.String(30), nullable=False)
    previous_value = db.Column(db.DateTime)
    requested_value = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="PENDENTE", index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    review_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    employee = db.relationship("Employee")
    time_record = db.relationship("TimeRecord", backref="corrections")
    reviewer = db.relationship("User")
