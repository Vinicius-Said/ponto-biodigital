from app.extensions import db
from app.services.clock import utc_now


class Schedule(db.Model):
    __tablename__ = "schedules"
    __table_args__ = (db.CheckConstraint("interval_minutes >= 0", name="positive_interval"),)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    interval_minutes = db.Column(db.Integer, nullable=False, default=60)
    saturday_start = db.Column(db.Time, nullable=False)
    saturday_end = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)


class EmployeeSchedule(db.Model):
    __tablename__ = "employee_schedules"
    __table_args__ = (
        db.UniqueConstraint("employee_id", "valid_from"),
        db.CheckConstraint("valid_until IS NULL OR valid_until >= valid_from", name="valid_dates"),
    )
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id"), nullable=False)
    valid_from = db.Column(db.Date, nullable=False)
    valid_until = db.Column(db.Date)
    cancelled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    schedule = db.relationship("Schedule")


class Holiday(db.Model):
    __tablename__ = "holidays"
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
