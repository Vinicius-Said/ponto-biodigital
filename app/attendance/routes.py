from datetime import datetime
from flask import Blueprint, request, redirect, url_for, render_template
from flask_login import login_required, current_user
from app.extensions import db
from app.models.time_record import TimeRecord

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')


@attendance_bp.route('/')
@login_required
def index():
    records = TimeRecord.query.filter_by(employee_id=current_user.employee_id).all()
    return render_template('attendance/index.html', records=records)


@attendance_bp.route('/register', methods=['POST'])
@login_required
def register():
    record_type = request.form.get('type')
    record = TimeRecord(
        employee_id=current_user.employee_id,
        type=record_type,
        recorded_at=datetime.utcnow(),
        ip_address=request.remote_addr
    )
    db.session.add(record)
    db.session.commit()
    return redirect(url_for('attendance.index'))
