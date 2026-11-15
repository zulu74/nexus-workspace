"""
Nexus Workspace — Identity & SSO service.

Every other service (chat, docs, mail, admin console) trusts a JWT
issued here instead of managing its own users/passwords — this is the
one place credentials and MFA live, which is the whole point of SSO:
one strong front door instead of five weak ones.
"""
import datetime

import pyotp
import qrcode
import qrcode.image.svg
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models, schemas, security
from .database import Base, SessionLocal, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nexus Identity & SSO")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer()


def log_event(db: Session, *, org_id: str, user_id: str | None, actor_email: str | None,
              event: str, detail: str | None = None, ip: str | None = None):
    entry = models.AuditLog(
        org_id=org_id, user_id=user_id, actor_email=actor_email,
        event=event, detail=detail, ip_address=ip,
    )
    db.add(entry)
    db.commit()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    try:
        payload = security.decode_access_token(creds.credentials)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.query(models.User).get(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or disabled")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


# --- Org signup / bootstrap -------------------------------------------------

@app.post("/auth/signup", response_model=schemas.TokenResponse)
def signup(payload: schemas.OrgSignupRequest, request: Request, db: Session = Depends(get_db)):
    if db.query(models.Organization).filter_by(domain=payload.org_domain).first():
        raise HTTPException(400, "Organization domain already registered")
    if db.query(models.User).filter_by(email=payload.admin_email).first():
        raise HTTPException(400, "Email already in use")

    org = models.Organization(name=payload.org_name, domain=payload.org_domain)
    db.add(org)
    db.flush()

    admin = models.User(
        org_id=org.id,
        email=payload.admin_email,
        full_name=payload.admin_full_name,
        password_hash=security.hash_password(payload.admin_password),
        role="admin",
    )
    db.add(admin)
    db.commit()

    log_event(db, org_id=org.id, user_id=admin.id, actor_email=admin.email,
              event="org_created", detail=f"org={org.domain}", ip=request.client.host)

    token = security.create_access_token(
        user_id=admin.id, org_id=org.id, role=admin.role, email=admin.email
    )
    return schemas.TokenResponse(access_token=token)


# --- Login / MFA -------------------------------------------------------------

@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=payload.email).first()
    ip = request.client.host

    if not user or not security.verify_password(payload.password, user.password_hash):
        if user:
            log_event(db, org_id=user.org_id, user_id=user.id, actor_email=payload.email,
                      event="login_failed_password", ip=ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    org = db.query(models.Organization).get(user.org_id)
    mfa_required = user.mfa_enabled or org.require_mfa

    if mfa_required:
        if not payload.mfa_code:
            return schemas.TokenResponse(access_token="", mfa_required=True)
        if not user.mfa_secret or not pyotp.TOTP(user.mfa_secret).verify(payload.mfa_code, valid_window=1):
            log_event(db, org_id=user.org_id, user_id=user.id, actor_email=user.email,
                      event="login_failed_mfa", ip=ip)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid MFA code")

    log_event(db, org_id=user.org_id, user_id=user.id, actor_email=user.email,
              event="login_success", ip=ip)

    token = security.create_access_token(
        user_id=user.id, org_id=user.org_id, role=user.role, email=user.email
    )
    return schemas.TokenResponse(access_token=token)


@app.post("/auth/mfa/enroll", response_model=schemas.MfaEnrollResponse)
def mfa_enroll(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    db.commit()
    otpauth_url = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Nexus Workspace")
    return schemas.MfaEnrollResponse(otpauth_url=otpauth_url, secret=secret)


@app.post("/auth/mfa/verify")
def mfa_verify(payload: schemas.MfaVerifyRequest, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    if not user.mfa_secret or not pyotp.TOTP(user.mfa_secret).verify(payload.code, valid_window=1):
        raise HTTPException(400, "Invalid code")
    user.mfa_enabled = True
    db.commit()
    log_event(db, org_id=user.org_id, user_id=user.id, actor_email=user.email, event="mfa_enabled")
    return {"mfa_enabled": True}


@app.get("/auth/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


# --- Admin: user management & org policy -------------------------------------

@app.get("/admin/users", response_model=list[schemas.UserOut])
def list_users(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(models.User).filter_by(org_id=admin.org_id).all()


@app.post("/admin/users", response_model=schemas.UserOut)
def create_user(payload: schemas.CreateUserRequest, admin: models.User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(email=payload.email).first():
        raise HTTPException(400, "Email already in use")
    new_user = models.User(
        org_id=admin.org_id,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=security.hash_password(payload.password),
        role=payload.role,
    )
    db.add(new_user)
    db.commit()
    log_event(db, org_id=admin.org_id, user_id=admin.id, actor_email=admin.email,
              event="user_created", detail=f"new_user={payload.email}")
    return new_user


@app.delete("/admin/users/{user_id}")
def deactivate_user(user_id: str, admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(models.User).filter_by(id=user_id, org_id=admin.org_id).first()
    if not target:
        raise HTTPException(404, "User not found")
    target.is_active = False
    db.commit()
    log_event(db, org_id=admin.org_id, user_id=admin.id, actor_email=admin.email,
              event="user_deactivated", detail=f"target={target.email}")
    return {"deactivated": target.email}


@app.get("/admin/org")
def get_org(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    org = db.query(models.Organization).get(admin.org_id)
    return {"id": org.id, "name": org.name, "domain": org.domain, "require_mfa": org.require_mfa}


@app.patch("/admin/org/policy")
def update_policy(payload: schemas.OrgPolicyUpdate, admin: models.User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    org = db.query(models.Organization).get(admin.org_id)
    org.require_mfa = payload.require_mfa
    db.commit()
    log_event(db, org_id=admin.org_id, user_id=admin.id, actor_email=admin.email,
              event="org_policy_updated", detail=f"require_mfa={payload.require_mfa}")
    return {"require_mfa": org.require_mfa}


@app.get("/admin/audit-log")
def audit_log(admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(models.AuditLog)
        .filter_by(org_id=admin.org_id)
        .order_by(models.AuditLog.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": r.id,
            "actor_email": r.actor_email,
            "event": r.event,
            "detail": r.detail,
            "ip_address": r.ip_address,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@app.get("/healthz")
def healthz():
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat()}
