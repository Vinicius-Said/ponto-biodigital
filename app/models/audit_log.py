from app.extensions import db
from app.services.clock import utc_now


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(80), nullable=False, index=True)
    entity = db.Column(db.String(80))
    entity_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)
    user = db.relationship("User")


class SystemState(db.Model):
    """Singleton from migration; serializes setup and last-director checks."""

    __tablename__ = "system_state"
    id = db.Column(db.Integer, primary_key=True)
    setup_completed = db.Column(db.Boolean, nullable=False, default=False)


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    username_digest = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)
