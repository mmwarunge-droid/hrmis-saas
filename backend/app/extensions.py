from flask import current_app
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


class InMemoryRedis:
    """Small Redis-compatible store used only by the isolated test config."""

    def __init__(self):
        self._values = {}

    def get(self, key):
        item = self._values.get(key)
        return item[0] if item else None

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self._values:
            return False
        self._values[key] = (str(value), ex)
        return True

    def delete(self, *keys):
        deleted = 0
        for key in keys:
            deleted += int(self._values.pop(key, None) is not None)
        return deleted

    def ping(self):
        return True


class RedisExtension:
    def init_app(self, app):
        if app.config.get('TESTING') or app.config['REDIS_URL'].startswith('memory://'):
            client = InMemoryRedis()
        else:
            from redis import Redis

            client = Redis.from_url(
                app.config['REDIS_URL'],
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
        app.extensions['redis_client'] = client

    @property
    def client(self):
        return current_app.extensions['redis_client']


bcrypt = Bcrypt()
cors = CORS()
db = SQLAlchemy()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)
migrate = Migrate()
redis_store = RedisExtension()
