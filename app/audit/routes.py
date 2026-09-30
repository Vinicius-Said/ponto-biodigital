from flask import Blueprint, render_template, request
from sqlalchemy import select
from app.extensions import db
from app.models import AuditLog
from app.services.audit import retention_cutoff
from app.services.permissions import require_director

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


@audit_bp.get("/")
@require_director
def index():
    action = request.args.get("action", "")[:80]
    query = select(AuditLog).where(AuditLog.created_at >= retention_cutoff())
    if action:
        query = query.where(AuditLog.action == action)
    pagination = db.paginate(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()), per_page=30, max_per_page=30
    )
    actions = list(
        db.session.scalars(
            select(AuditLog.action)
            .where(AuditLog.created_at >= retention_cutoff())
            .distinct()
            .order_by(AuditLog.action)
        )
    )
    return render_template("audit/index.html", pagination=pagination, actions=actions, selected_action=action)
