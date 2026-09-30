from functools import wraps
from flask import abort
from flask_login import current_user, login_required


def require_role(role):
    def decorate(function):
        @wraps(function)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.is_active or current_user.role != role:
                abort(403)
            return function(*args, **kwargs)

        return wrapped

    return decorate


require_director = require_role("DIRETORIA")
require_employee = require_role("FUNCIONARIO")
