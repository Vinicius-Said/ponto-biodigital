from datetime import datetime
from app.extensions import db

class CorrectionRequest(db.Model):
    __tablename__ = 'correction_requests'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    time_record_id = db.Column(db.Integer)
    requested_value = db.Column(db.DateTime)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDENTE')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
