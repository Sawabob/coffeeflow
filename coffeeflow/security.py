"""Сесія адміністратора, CSRF і локальне обмеження частоти запитів."""
from collections import defaultdict, deque
from functools import wraps
import hashlib
import secrets
from threading import Lock
import time
from flask import current_app, g, request, session
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from .db import get_db
from .errors import APIError


def owner_hash():
    if 'guest_id' not in session:
        session['guest_id'] = secrets.token_urlsafe(32)
    return hashlib.sha256(session['guest_id'].encode()).hexdigest()


def serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='coffeeflow-csrf-v1')


def csrf_token():
    owner_hash()
    if 'csrf_nonce' not in session:
        session['csrf_nonce'] = secrets.token_urlsafe(32)
    return serializer().dumps(session['csrf_nonce'])


def rotate_session(admin_id=None):
    guest = session.get('guest_id', secrets.token_urlsafe(32))
    session.clear()
    session['guest_id'] = guest
    if admin_id is not None:
        session['admin_id'] = admin_id
        session.permanent = True


def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.admin is None:
            raise APIError('authentication_required', 'Потрібен вхід адміністратора.', 401)
        return view(*args, **kwargs)
    return wrapped


class RateLimiter:
    """Один процес: захист демо, не розподілена система лімітів."""
    def __init__(self):
        self.entries, self.lock = defaultdict(deque), Lock()

    def check(self, key, limit, window):
        now = time.monotonic()
        with self.lock:
            # Bounded lifetime, even when addresses change.
            for stale in [k for k, q in self.entries.items() if q[-1] <= now-window]:
                del self.entries[stale]
            q = self.entries[key]
            while q and q[0] <= now-window:
                q.popleft()
            if len(q) >= limit:
                raise APIError('rate_limit_exceeded', 'Забагато запитів; повторіть через 15 хвилин.', 429)
            q.append(now)


def install_security(app):
    app.extensions['rate_limiter'] = RateLimiter()

    @app.before_request
    def protect_request():
        from .validation import integer
        for field, value in (request.view_args or {}).items():
            if field.endswith('_id'):
                integer(value, field)
        g.admin = None
        if 'admin_id' in session:
            g.admin = get_db().execute('SELECT id, username FROM admins WHERE id=?',
                                      (session['admin_id'],)).fetchone()
        if not request.path.startswith('/api/v1/'):
            return
        if request.method == 'POST' and app.config['RATE_LIMIT_ENABLED']:
            limits = {'/api/v1/auth/login': 10, '/api/v1/orders': 30}
            if request.path in limits:
                app.extensions['rate_limiter'].check(
                    (request.path, request.remote_addr), limits[request.path], 900)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            token = request.headers.get('X-CSRFToken', '')
            try:
                nonce = serializer().loads(token, max_age=3600)
                valid = isinstance(nonce, str) and secrets.compare_digest(
                    nonce, session.get('csrf_nonce', ''))
            except (BadSignature, SignatureExpired):
                valid = False
            if not valid:
                raise APIError('csrf_failed', 'Отримайте CSRF-токен і передайте X-CSRFToken з тією ж cookie.', 400)

    @app.after_request
    def secure_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        if response.status_code == 429:
            response.headers['Retry-After'] = '900'
        return response
