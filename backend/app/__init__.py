import logging
import os
from pathlib import Path

from flask import Flask, request
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from app.config import config_by_name
from app.extensions import bcrypt, cors, db, jwt, limiter, migrate, redis_store
from app.routes import register_blueprints
from app.utils.response import fail, success


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the HRMIS Flask application."""
    environment = (config_name or os.getenv('APP_ENV') or os.getenv('FLASK_ENV') or 'development').lower()
    config_class = config_by_name.get(environment)
    if config_class is None:
        valid = ', '.join(sorted(config_by_name))
        raise RuntimeError(f'Unknown application environment {environment!r}. Expected one of: {valid}')

    if environment == 'production':
        config_class.validate()

    app = Flask(__name__)
    app.config.from_object(config_class)

    _configure_logging(app)
    _initialize_extensions(app)
    _register_jwt_callbacks()
    _register_error_handlers(app)
    _register_health_endpoints(app)
    _register_cli(app)
    register_blueprints(app)

    if not app.config.get('TESTING'):
        Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

    return app


def _initialize_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)
    redis_store.init_app(app)

    api_prefix = app.config['API_PREFIX'].rstrip('/')
    cors.init_app(
        app,
        resources={
            f'{api_prefix}/*': {
                'origins': app.config['CORS_ORIGINS'],
                'allow_headers': ['Content-Type', 'X-CSRF-TOKEN', 'X-Request-ID'],
                'expose_headers': ['X-Request-ID'],
                'methods': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
                'max_age': 600,
                'supports_credentials': True,
            }
        },
    )


def _register_jwt_callbacks() -> None:
    from app.models import User
    from app.services.session_service import is_token_revoked

    @jwt.user_lookup_loader
    def load_user(_jwt_header, jwt_data):
        user = db.session.get(User, jwt_data['sub'])
        if not user or not user.is_active or user.deleted_at is not None:
            return None
        return user

    @jwt.user_lookup_error_loader
    def user_lookup_failed(_jwt_header, _jwt_data):
        return fail('INVALID_TOKEN', 'The token user no longer exists or is inactive', 401)

    @jwt.unauthorized_loader
    def missing_token(reason):
        return fail('AUTHENTICATION_REQUIRED', reason, 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return fail('INVALID_TOKEN', reason, 401)

    @jwt.expired_token_loader
    def expired_token(_jwt_header, _jwt_data):
        return fail('TOKEN_EXPIRED', 'The token has expired', 401)

    @jwt.token_in_blocklist_loader
    def token_in_blocklist(_jwt_header, jwt_data):
        return is_token_revoked(jwt_data)

    @jwt.revoked_token_loader
    def revoked_token(_jwt_header, _jwt_data):
        return fail('TOKEN_REVOKED', 'The token has been revoked', 401)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        code = error.name.upper().replace(' ', '_')
        return fail(code, error.description, error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        db.session.rollback()
        app.logger.exception('Unhandled application error')
        if app.config.get('TESTING'):
            raise error
        return fail('INTERNAL_SERVER_ERROR', 'An unexpected error occurred', 500)

    @app.after_request
    def add_response_headers(response):
        request_id = request.headers.get('X-Request-ID')
        if request_id:
            response.headers['X-Request-ID'] = request_id[:128]
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'no-referrer')
        return response


def _register_health_endpoints(app: Flask) -> None:
    @app.get('/health')
    @limiter.exempt
    def health():
        return success({'status': 'ok', 'environment': app.config['ENVIRONMENT']})

    @app.get('/ready')
    @limiter.exempt
    def readiness():
        try:
            db.session.execute(text('SELECT 1'))
            redis_store.client.ping()
        except Exception:
            db.session.rollback()
            app.logger.exception('Readiness database check failed')
            return fail('NOT_READY', 'Database or Redis connectivity check failed', 503)
        return success({'status': 'ready'})


def _register_cli(app: Flask) -> None:
    from app.cli import register_commands

    register_commands(app)


def _configure_logging(app: Flask) -> None:
    if not app.debug and not app.testing:
        app.logger.setLevel(logging.INFO)
