import base64
import hashlib
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / '.env')


def _csv(value: str | None) -> list[str]:
    if not value:
        return ['http://localhost:5173']
    return [item.strip() for item in value.split(',') if item.strip()]


def _csv_or_default(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return list(default)
    return [item.strip() for item in value.split(',') if item.strip()]


def _derived_fernet_key(secret: str) -> str:
    digest = hashlib.sha256(f'hrmis-mfa:{secret}'.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii')


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _database_url(default: str) -> str:
    url = os.getenv('DATABASE_URL', default)
    # Render sometimes exposes postgres://; SQLAlchemy requires postgresql://.
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class BaseConfig:
    ENVIRONMENT = 'base'
    API_PREFIX = os.getenv('API_PREFIX', '/api')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-change-me')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv('TOKEN_EXPIRY_MINUTES', '60')))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv('REFRESH_TOKEN_EXPIRY_DAYS', '14')))
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_COOKIE_DOMAIN = os.getenv('JWT_COOKIE_DOMAIN') or None
    JWT_ACCESS_COOKIE_PATH = f"{API_PREFIX.rstrip('/')}/"
    JWT_REFRESH_COOKIE_PATH = f"{API_PREFIX.rstrip('/')}/auth/refresh"
    # The SPA reads only the random CSRF values; the JWT cookies remain HttpOnly.
    JWT_ACCESS_CSRF_COOKIE_PATH = '/'
    JWT_REFRESH_CSRF_COOKIE_PATH = '/'
    JWT_ACCESS_CSRF_HEADER_NAME = 'X-CSRF-TOKEN'
    JWT_REFRESH_CSRF_HEADER_NAME = 'X-CSRF-TOKEN'
    SQLALCHEMY_DATABASE_URI = _database_url(f"sqlite:///{BASE_DIR / 'dev.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    CORS_ORIGINS = _csv(os.getenv('CORS_ORIGINS') or FRONTEND_URL)
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(10 * 1024 * 1024)))
    JSON_SORT_KEYS = False
    ERROR_INCLUDE_MESSAGE = False
    REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    REDIS_KEY_PREFIX = os.getenv('REDIS_KEY_PREFIX', 'hrmis:auth')
    AUTH_MAX_FAILED_ATTEMPTS = int(os.getenv('AUTH_MAX_FAILED_ATTEMPTS', '5'))
    AUTH_FAILURE_WINDOW_MINUTES = int(os.getenv('AUTH_FAILURE_WINDOW_MINUTES', '15'))
    AUTH_LOCKOUT_MINUTES = int(os.getenv('AUTH_LOCKOUT_MINUTES', '15'))
    AUTH_SUSPICIOUS_LOGIN_ENABLED = _bool_env('AUTH_SUSPICIOUS_LOGIN_ENABLED', True)
    PASSWORD_RESET_TOKEN_MINUTES = int(os.getenv('PASSWORD_RESET_TOKEN_MINUTES', '30'))
    EMAIL_VERIFICATION_TOKEN_HOURS = int(os.getenv('EMAIL_VERIFICATION_TOKEN_HOURS', '24'))
    MFA_REQUIRED_ROLES = _csv_or_default(os.getenv('MFA_REQUIRED_ROLES'), ['SUPER_ADMIN', 'CLIENT_ADMIN'])
    MFA_CHALLENGE_MINUTES = int(os.getenv('MFA_CHALLENGE_MINUTES', '5'))
    MFA_MAX_CHALLENGE_ATTEMPTS = int(os.getenv('MFA_MAX_CHALLENGE_ATTEMPTS', '5'))
    MFA_TOTP_ISSUER = os.getenv('MFA_TOTP_ISSUER', 'HRMIS')
    MFA_TOTP_VALID_WINDOW = int(os.getenv('MFA_TOTP_VALID_WINDOW', '1'))
    MFA_RECOVERY_CODE_COUNT = int(os.getenv('MFA_RECOVERY_CODE_COUNT', '10'))
    MFA_ENCRYPTION_KEYS = _csv_or_default(
        os.getenv('MFA_ENCRYPTION_KEYS'),
        [_derived_fernet_key(SECRET_KEY)],
    )
    MFA_RECOVERY_CODE_PEPPER = os.getenv(
        'MFA_RECOVERY_CODE_PEPPER',
        hashlib.sha256(f'hrmis-mfa-recovery:{SECRET_KEY}'.encode('utf-8')).hexdigest(),
    )
    PASSWORD_RESET_URL = os.getenv('PASSWORD_RESET_URL', f'{FRONTEND_URL}/reset-password')
    EMAIL_VERIFICATION_URL = os.getenv('EMAIL_VERIFICATION_URL', f'{FRONTEND_URL}/verify-email')
    MAIL_TRANSPORT = os.getenv('MAIL_TRANSPORT', 'console')
    MAIL_FROM = os.getenv('MAIL_FROM', 'no-reply@localhost')
    MAIL_SMTP_HOST = os.getenv('MAIL_SMTP_HOST', '127.0.0.1')
    MAIL_SMTP_PORT = int(os.getenv('MAIL_SMTP_PORT', '587'))
    MAIL_SMTP_USERNAME = os.getenv('MAIL_SMTP_USERNAME') or None
    MAIL_SMTP_PASSWORD = os.getenv('MAIL_SMTP_PASSWORD') or None
    MAIL_SMTP_USE_TLS = _bool_env('MAIL_SMTP_USE_TLS', True)
    MAIL_SMTP_TIMEOUT_SECONDS = int(os.getenv('MAIL_SMTP_TIMEOUT_SECONDS', '10'))
    TRUST_PROXY_HEADERS = _bool_env('TRUST_PROXY_HEADERS', False)
    RATELIMIT_DEFAULT = os.getenv('RATELIMIT_DEFAULT', '200 per day;50 per hour')
    RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_HEADERS_ENABLED = True


class DevelopmentConfig(BaseConfig):
    ENVIRONMENT = 'development'
    DEBUG = True
    FLASK_ENV = 'development'


class TestingConfig(BaseConfig):
    ENVIRONMENT = 'testing'
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    REDIS_URL = 'memory://testing'
    MAIL_TRANSPORT = 'memory'
    PASSWORD_RESET_URL = 'https://frontend.test/reset-password'
    EMAIL_VERIFICATION_URL = 'https://frontend.test/verify-email'
    MFA_REQUIRED_ROLES = []


class ProductionConfig(BaseConfig):
    ENVIRONMENT = 'production'
    DEBUG = False
    FLASK_ENV = 'production'
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = os.getenv('JWT_COOKIE_SAMESITE', 'Lax')

    @classmethod
    def validate(cls):
        missing = [
            key
            for key in (
                'SECRET_KEY',
                'JWT_SECRET_KEY',
                'DATABASE_URL',
                'REDIS_URL',
                'MFA_ENCRYPTION_KEYS',
                'MFA_RECOVERY_CODE_PEPPER',
            )
            if not os.getenv(key)
        ]
        if missing:
            raise RuntimeError(f"Missing required production environment variables: {', '.join(missing)}")

        secret_key = os.environ['SECRET_KEY']
        jwt_secret = os.environ['JWT_SECRET_KEY']
        if len(secret_key) < 32 or len(jwt_secret) < 32:
            raise RuntimeError('SECRET_KEY and JWT_SECRET_KEY must each contain at least 32 characters')
        if secret_key == jwt_secret:
            raise RuntimeError('SECRET_KEY and JWT_SECRET_KEY must be different values')
        try:
            from cryptography.fernet import Fernet

            for key in cls.MFA_ENCRYPTION_KEYS:
                Fernet(key.encode('ascii'))
        except (ValueError, TypeError) as exc:
            raise RuntimeError('MFA_ENCRYPTION_KEYS must contain valid Fernet keys') from exc
        if len(cls.MFA_RECOVERY_CODE_PEPPER) < 32:
            raise RuntimeError('MFA_RECOVERY_CODE_PEPPER must contain at least 32 characters')
        if cls.MFA_RECOVERY_CODE_PEPPER in {secret_key, jwt_secret}:
            raise RuntimeError('MFA_RECOVERY_CODE_PEPPER must differ from SECRET_KEY and JWT_SECRET_KEY')
        if cls.JWT_COOKIE_SAMESITE.lower() == 'none' and not cls.JWT_COOKIE_SECURE:
            raise RuntimeError('JWT_COOKIE_SECURE must be enabled when JWT_COOKIE_SAMESITE=None')
        if cls.MAIL_TRANSPORT.lower() != 'smtp':
            raise RuntimeError('MAIL_TRANSPORT must be smtp in production')
        if not cls.MAIL_SMTP_USE_TLS:
            raise RuntimeError('MAIL_SMTP_USE_TLS must be enabled in production')
        mail_missing = [key for key in ('MAIL_FROM', 'MAIL_SMTP_HOST') if not os.getenv(key)]
        if mail_missing:
            raise RuntimeError(f"Missing required production email variables: {', '.join(mail_missing)}")
        account_urls = {
            'PASSWORD_RESET_URL': cls.PASSWORD_RESET_URL,
            'EMAIL_VERIFICATION_URL': cls.EMAIL_VERIFICATION_URL,
        }
        insecure_urls = [name for name, value in account_urls.items() if not value.startswith('https://')]
        if insecure_urls:
            raise RuntimeError(f"Production account URLs must use HTTPS: {', '.join(insecure_urls)}")


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
