"""
Nexus Workspace — Mail service.

Intra-organization mail: compose, inbox, sent, mark-as-read. Recipient
must belong to the same org_id as the sender — scoped exactly like
chat and docs, via the same JWT SSO pattern. Real cross-domain SMTP
delivery (MX records, SPF/DKIM/DMARC) is a different, much larger
problem than this demo takes on — see README.
"""
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from . import models, security
from .database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nexus Mail")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/app", StaticFiles(directory="static", html=True), name="static")

bearer_scheme = HTTPBearer()


class Claims(BaseModel):
    user_id: str
    org_id: str
    email: str


def get_claims(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Claims:
    try:
        payload = security.require_claims(creds.credentials)
    except security.InvalidToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return Claims(user_id=payload["sub"], org_id=payload["org_id"], email=payload["email"])


class ComposeRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str


@app.post("/mail/send")
def send_mail(payload: ComposeRequest, claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    mail = models.Mail(
        org_id=claims.org_id, from_email=claims.email, to_email=payload.to_email,
        subject=payload.subject, body=payload.body,
    )
    db.add(mail)
    db.commit()
    return {"id": mail.id, "sent": True}


@app.get("/mail/inbox")
def inbox(claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    rows = (
        db.query(models.Mail)
        .filter_by(org_id=claims.org_id, to_email=claims.email)
        .order_by(models.Mail.created_at.desc())
        .all()
    )
    return [_serialize(r) for r in rows]


@app.get("/mail/sent")
def sent(claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    rows = (
        db.query(models.Mail)
        .filter_by(org_id=claims.org_id, from_email=claims.email)
        .order_by(models.Mail.created_at.desc())
        .all()
    )
    return [_serialize(r) for r in rows]


@app.post("/mail/{mail_id}/read")
def mark_read(mail_id: str, claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    mail = db.query(models.Mail).filter_by(id=mail_id, org_id=claims.org_id, to_email=claims.email).first()
    if not mail:
        raise HTTPException(404, "Message not found")
    mail.is_read = True
    db.commit()
    return {"read": True}


def _serialize(r: models.Mail) -> dict:
    return {
        "id": r.id, "from_email": r.from_email, "to_email": r.to_email,
        "subject": r.subject, "body": r.body, "is_read": r.is_read,
        "created_at": r.created_at.isoformat(),
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
