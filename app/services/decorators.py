from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(role):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role != role:
                abort(403)
            return function(*args, **kwargs)
        return wrapper
    return decorator


def director_required(function):
    return role_required('DIRETORIA')(function)


def employee_required(function):
    return role_required('FUNCIONARIO')(function)
