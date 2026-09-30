from datetime import datetime
from app.extensions import db

class TimeRecord(db.Model):
    __tablename__ = 'time_records'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    type = db.Column(db.String(30), nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
