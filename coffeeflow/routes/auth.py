from flask import Blueprint, current_app, jsonify, g
from werkzeug.security import check_password_hash
from ..db import get_db
from ..errors import APIError
from ..security import csrf_token, rotate_session, require_admin
from ..validation import body, string, fail

bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')


@bp.get('/csrf')
def csrf():
    return jsonify(csrf_token=csrf_token())


@bp.post('/login')
def login():
    data = body({'username','password'}, {'username','password'})
    username = string(data['username'], 'username', 3, 40).lower()
    password = data['password']
    if not isinstance(password, str) or not 1 <= len(password) <= 128:
        fail('password', 'Довжина пароля 1–128 символів.')
    admin = get_db().execute('SELECT * FROM admins WHERE username=?', (username,)).fetchone()
    valid = check_password_hash(admin['password_hash'] if admin else current_app.config['DUMMY_HASH'], password)
    if admin is None or not valid:
        raise APIError('invalid_credentials', 'Неправильний логін або пароль.', 401)
    rotate_session(admin['id'])
    return jsonify(admin={'id': admin['id'], 'username': admin['username']}, csrf_token=csrf_token())


@bp.get('/me')
@require_admin
def me():
    return jsonify(admin=dict(g.admin))


@bp.post('/logout')
@require_admin
def logout():
    rotate_session()
    return '', 204
