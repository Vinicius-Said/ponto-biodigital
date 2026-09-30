from flask import Blueprint, request, redirect, url_for, render_template
from flask_login import login_required
from app.services.decorators import director_required
from app.extensions import db
from app.models.employee import Employee

employees_bp = Blueprint('employees', __name__, url_prefix='/employees')


@employees_bp.route('/')
@login_required
@director_required
def index():
    employees = Employee.query.all()
    return render_template('employees/index.html', employees=employees)


@employees_bp.route('/create', methods=['GET', 'POST'])
@login_required
@director_required
def create():
    if request.method == 'POST':
        employee = Employee(name=request.form.get('name'))
        db.session.add(employee)
        db.session.commit()
        return redirect(url_for('employees.index'))

    return render_template('employees/create.html')
