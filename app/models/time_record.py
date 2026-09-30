from app.extensions import db
from app.services.clock import utc_now

RECORD_TYPES = ("ENTRADA", "INTERVALO_SAIDA", "INTERVALO_RETORNO", "SAIDA")
RECORD_LABELS = {
    "ENTRADA": "Entrada",
    "INTERVALO_SAIDA": "Saída para intervalo",
    "INTERVALO_RETORNO": "Retorno do intervalo",
    "SAIDA": "Saída",
}


class TimeRecord(db.Model):
    __tablename__ = "time_records"
    __table_args__ = (
        db.UniqueConstraint("employee_id", "work_date", "type"),
        db.CheckConstraint("type IN ('ENTRADA', 'INTERVALO_SAIDA', 'INTERVALO_RETORNO', 'SAIDA')", name="valid_type"),
        db.CheckConstraint("source IN ('SERVIDOR', 'CORRECAO')", name="valid_source"),
        db.Index("ix_time_records_employee_date", "employee_id", "work_date"),
    )
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    work_date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(30), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False)
    corrected_at = db.Column(db.DateTime)
    ip_address = db.Column(db.String(45))
    source = db.Column(db.String(16), nullable=False, default="SERVIDOR")
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    @property
    def effective_at(self):
        return self.corrected_at or self.recorded_at
