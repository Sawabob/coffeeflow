"""Фабрика застосунку. Python 3.11+; Flask 3.1."""
from datetime import datetime, timedelta, timezone
import os
import json
from pathlib import Path
import secrets
from flask import Flask, jsonify, render_template
from werkzeug.security import generate_password_hash
from .db import get_db, close_db
from .errors import register_errors
from .security import install_security


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    instance = Path(app.instance_path)
    instance.mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        DATABASE=str(instance / 'coffeeflow.sqlite3'),
        SECRET_KEY=os.environ.get('COFFEEFLOW_SECRET_KEY'),
        SESSION_COOKIE_NAME='coffeeflow_session', SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COFFEEFLOW_HTTPS') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=32*1024, RATE_LIMIT_ENABLED=True,
        NOW=lambda: datetime.now(timezone.utc),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config['SECRET_KEY']:
        if os.environ.get('COFFEEFLOW_ENV') == 'production':
            raise RuntimeError('Set COFFEEFLOW_SECRET_KEY for production.')
        secret_path = instance / '.secret-key'
        try:
            with secret_path.open('x', encoding='utf-8') as handle:
                handle.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = secret_path.read_text(encoding='utf-8').strip()
    if len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('Secret key must contain at least 32 characters.')
    app.config['DUMMY_HASH'] = generate_password_hash(secrets.token_urlsafe(32))
    app.json.ensure_ascii = False
    app.teardown_appcontext(close_db)
    register_errors(app)
    install_security(app)
    from .routes import auth, catalog, orders
    from .cli import register_cli
    for bp in (auth.bp, catalog.bp, orders.bp):
        app.register_blueprint(bp)
    register_cli(app)

    @app.get('/')
    def index():
        return render_template('shop.html', page='shop')

    @app.get('/checkout')
    def checkout_page():
        return render_template('checkout.html', page='checkout')

    @app.get('/orders')
    @app.get('/orders/<int:order_id>')
    def orders_page(order_id=None):
        return render_template('orders.html', page='orders', order_id=order_id)

    @app.get('/admin')
    def admin_page():
        return render_template('admin.html', page='admin')

    @app.get('/api/v1/health')
    def health():
        get_db().execute('SELECT id FROM orders LIMIT 1').fetchone()
        return jsonify(status='ok')

    @app.get('/api/v1/openapi.json')
    def openapi():
        spec = Path(app.root_path).parent / 'docs' / 'openapi.json'
        return jsonify(json.loads(spec.read_text(encoding='utf-8')))

    return app
