from typing import Optional

from pydantic import BaseModel, EmailStr


class OrgSignupRequest(BaseModel):
    org_name: str
    org_domain: str
    admin_full_name: str
    admin_email: EmailStr
    admin_password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    mfa_required: bool = False


class MfaEnrollResponse(BaseModel):
    otpauth_url: str
    secret: str


class MfaVerifyRequest(BaseModel):
    code: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    mfa_enabled: bool
    is_active: bool

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "member"


class OrgPolicyUpdate(BaseModel):
    require_mfa: bool


class AuditLogOut(BaseModel):
    id: str
    actor_email: Optional[str]
    event: str
    detail: Optional[str]
    ip_address: Optional[str]
    created_at: str

    class Config:
        from_attributes = True
