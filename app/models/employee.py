from app.extensions import db
from app.services.clock import utc_now


class Employee(db.Model):
    __tablename__ = "employees"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    hired_on = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    users = db.relationship("User", backref="employee", lazy="select")
    records = db.relationship("TimeRecord", backref="employee", lazy="select")
    assignments = db.relationship(
        "EmployeeSchedule", backref="employee", order_by="EmployeeSchedule.valid_from", lazy="select"
    )
