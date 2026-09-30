import calendar
from datetime import timedelta
from flask import has_request_context, request
from flask_login import current_user
from sqlalchemy import delete
from app.extensions import db
from app.models import AuditLog, LoginAttempt
from app.services.clock import utc_now


def write_audit(action, entity=None, entity_id=None, details=None, actor_id=None):
    if actor_id is None and has_request_context() and current_user.is_authenticated:
        actor_id = current_user.id
    log = AuditLog(
        user_id=actor_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details or {},
        ip_address=request.remote_addr if has_request_context() else None,
    )
    db.session.add(log)
    return log


def retention_cutoff(now=None):
    now = now or utc_now()
    month_index = now.year * 12 + now.month - 1 - 3
    year, zero_month = divmod(month_index, 12)
    month = zero_month + 1
    day = min(now.day, calendar.monthrange(year, month)[1])
    return now.replace(year=year, month=month, day=day)


def prune_logs():
    count = db.session.execute(delete(AuditLog).where(AuditLog.created_at < retention_cutoff())).rowcount
    db.session.execute(delete(LoginAttempt).where(LoginAttempt.created_at < utc_now() - timedelta(days=1)))
    db.session.commit()
    return count
