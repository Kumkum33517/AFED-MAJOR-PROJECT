"""Password hashing and JWTs. bcrypt is used directly: it only accepts the first 72 bytes."""
import hashlib
from datetime import timedelta

import bcrypt
from jose import JWTError, jwt

from .config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from .models import utcnow


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode()[:72], password_hash.encode())


def password_version(password_hash: str) -> str:
    """Goes in the token, so changing a password ends every session made with the old one."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_token(user_id: int, password_hash: str) -> str:
    claims = {"sub": str(user_id), "pv": password_version(password_hash), "exp": utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)}
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> tuple[int, str] | None:
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(claims["sub"]), str(claims["pv"])
    except (JWTError, KeyError, ValueError):
        return None
