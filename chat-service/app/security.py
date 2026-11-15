"""
Must stay in sync with identity-service's token issuance — same shared
secret, same algorithm. This is the "every service trusts the identity
service's JWT" half of SSO; identity-service never has to know chat
exists, and chat never handles a password.
"""
import os
from jose import jwt, JWTError

JWT_SECRET = os.environ.get("NEXUS_JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


class InvalidToken(Exception):
    pass


def require_claims(token: str) -> dict:
    try:
        return decode_access_token(token)
    except JWTError as exc:
        raise InvalidToken(str(exc))
