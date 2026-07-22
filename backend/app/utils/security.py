import hmac
from app.extensions import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.generate_password_hash(password).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    return hmac.compare_digest(str(bcrypt.check_password_hash(password_hash, password)), 'True')
