from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

bcrypt = Bcrypt()
cors = CORS()
db = SQLAlchemy()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)
migrate = Migrate()
