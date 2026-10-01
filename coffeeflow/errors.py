"""Єдиний формат помилок API."""
from flask import jsonify
from werkzeug.exceptions import HTTPException
import sqlite3


class APIError(Exception):
    def __init__(self, code, message, status=422, fields=None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.fields = fields or {}


def register_errors(app):
    @app.errorhandler(APIError)
    def api_error(exc):
        return jsonify(error=dict(code=exc.code, message=exc.message,
                                  fields=exc.fields)), exc.status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        # Keep protocol headers, notably Allow for 405.
        response = exc.get_response()
        response.data = app.json.dumps({'error': {
            'code': f'http_{exc.code}', 'message': exc.name, 'fields': {}}})
        response.content_type = 'application/json'
        return response

    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(exc):
        return jsonify(error=dict(code='conflict',
            message='Дані конфліктують з наявними записами.', fields={})), 409

    @app.errorhandler(sqlite3.OperationalError)
    def database_unavailable(exc):
        app.logger.error('Database operation failed: %s', type(exc).__name__)
        return jsonify(error=dict(code='database_unavailable',
            message='База недоступна. Перевірте ініціалізацію або повторіть запит.',
            fields={})), 503, {'Retry-After': '1'}

    @app.errorhandler(500)
    def internal_error(exc):
        return jsonify(error=dict(code='internal_error',
            message='Внутрішня помилка сервера.', fields={})), 500
