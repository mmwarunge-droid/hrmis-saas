import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, g, has_request_context, request
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from app.config import config_by_name
from app.extensions import bcrypt, cors, db, jwt, limiter, migrate, redis_store
from app.routes import register_blueprints
from app.utils.response import fail, success


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if has_request_context():
            payload.update({
                'request_id': getattr(g, 'request_id', None),
                'method': request.method,
                'path': request.path,
            })
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Kinetic Flask application."""
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
    # Register request metadata before extensions that may short-circuit
    # requests, such as rate limiting.
    _register_request_context(app)
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


def _register_request_context(app: Flask) -> None:
    @app.before_request
    def establish_request_context():
        supplied = request.headers.get('X-Request-ID', '').strip()
        g.request_id = supplied[:128] if supplied else str(uuid4())
        g.request_started_at = time.perf_counter()

    @app.after_request
    def log_completed_request(response):
        started_at = getattr(g, 'request_started_at', None)
        elapsed_ms = (
            round((time.perf_counter() - started_at) * 1000, 2)
            if started_at is not None
            else None
        )

        request_id = getattr(g, 'request_id', None)
        if not request_id:
            supplied = request.headers.get('X-Request-ID', '').strip()
            request_id = supplied[:128] if supplied else str(uuid4())
            g.request_id = request_id

        response.headers['X-Request-ID'] = request_id
        if elapsed_ms is not None:
            response.headers['Server-Timing'] = f'app;dur={elapsed_ms}'

        if request.path not in {'/health', '/ready'}:
            app.logger.info(
                'request.complete status=%s duration_ms=%s',
                response.status_code,
                elapsed_ms if elapsed_ms is not None else 'unavailable',
            )

        return response


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
    from app.utils.decorators import TenantContextRequired

    @app.errorhandler(TenantContextRequired)
    def handle_tenant_context_required(error):
        return fail(
            'TENANT_CONTEXT_REQUIRED',
            str(error),
            422,
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if error.code == 429:
            return fail(
                'RATE_LIMIT_EXCEEDED',
                'Too many requests. Please wait and try again.',
                429,
            )

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
    def add_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
        )
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-site')
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        if request.path.startswith(app.config['API_PREFIX']):
            response.headers.setdefault('Cache-Control', 'no-store')
        if app.config['ENVIRONMENT'] == 'production':
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )
        return response


def _register_health_endpoints(app: Flask) -> None:
    @app.get('/health')
    @limiter.exempt
    def health():
        return success({
            'status': 'ok',
            'environment': app.config['ENVIRONMENT'],
            'release': app.config['RELEASE_SHA'],
        })

    @app.get('/ready')
    @limiter.exempt
    def readiness():
        checks = {'database': 'unknown', 'redis': 'unknown'}
        try:
            db.session.execute(text('SELECT 1'))
            checks['database'] = 'ready'
            redis_store.client.ping()
            checks['redis'] = 'ready'
        except Exception:
            db.session.rollback()
            app.logger.exception('Readiness dependency check failed')
            return fail(
                'NOT_READY',
                'Database or Redis connectivity check failed',
                503,
            )
        return success({'status': 'ready', 'checks': checks})


def _register_cli(app: Flask) -> None:
    from app.cli import register_commands

    register_commands(app)


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.debug else logging.INFO
    app.logger.setLevel(level)
    if app.config.get('JSON_LOGS'):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        app.logger.handlers.clear()
        app.logger.addHandler(handler)
        app.logger.propagate = False
