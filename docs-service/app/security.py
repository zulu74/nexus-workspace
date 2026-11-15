import os
from jose import jwt, JWTError

JWT_SECRET = os.environ.get("NEXUS_JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"


class InvalidToken(Exception):
    pass


def require_claims(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidToken(str(exc))
