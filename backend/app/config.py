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
    CORS_ORIGINS = _csv(os.getenv('CORS_ORIGINS') or os.getenv('FRONTEND_URL'))
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(10 * 1024 * 1024)))
    JSON_SORT_KEYS = False
    ERROR_INCLUDE_MESSAGE = False
    REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    REDIS_KEY_PREFIX = os.getenv('REDIS_KEY_PREFIX', 'hrmis:auth')
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


class ProductionConfig(BaseConfig):
    ENVIRONMENT = 'production'
    DEBUG = False
    FLASK_ENV = 'production'
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = os.getenv('JWT_COOKIE_SAMESITE', 'Lax')

    @classmethod
    def validate(cls):
        missing = [key for key in ('SECRET_KEY', 'JWT_SECRET_KEY', 'DATABASE_URL', 'REDIS_URL') if not os.getenv(key)]
        if missing:
            raise RuntimeError(f"Missing required production environment variables: {', '.join(missing)}")

        secret_key = os.environ['SECRET_KEY']
        jwt_secret = os.environ['JWT_SECRET_KEY']
        if len(secret_key) < 32 or len(jwt_secret) < 32:
            raise RuntimeError('SECRET_KEY and JWT_SECRET_KEY must each contain at least 32 characters')
        if secret_key == jwt_secret:
            raise RuntimeError('SECRET_KEY and JWT_SECRET_KEY must be different values')
        if cls.JWT_COOKIE_SAMESITE.lower() == 'none' and not cls.JWT_COOKIE_SECURE:
            raise RuntimeError('JWT_COOKIE_SECURE must be enabled when JWT_COOKIE_SAMESITE=None')


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
