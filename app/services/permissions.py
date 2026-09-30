from functools import wraps
from flask import abort
from flask_login import current_user


def require_role(role):
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


def require_director(function):
    return require_role('DIRETORIA')(function)


def require_employee(function):
    return require_role('FUNCIONARIO')(function)
