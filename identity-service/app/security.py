"""
Shared JWT logic. In production this would be RS256 with a JWKS endpoint
other services fetch and cache — a shared HS256 secret is the simplified
version for a self-contained demo, and is called out as such in the README.
"""
import datetime
import os

from jose import jwt
from passlib.context import CryptContext

JWT_SECRET = os.environ.get("NEXUS_JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(*, user_id: str, org_id: str, role: str, email: str) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iss": "nexus-identity",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
