"""
Nexus Workspace — Docs service.

Simplified collaborative docs: every save creates a new immutable
version rather than overwriting in place, so nothing is ever lost to
a bad edit — the same reasoning a real document platform uses, just
without operational-transform/CRDT merge logic for simultaneous
editors (noted as a real next step in the README, not pretended away).
"""
import datetime

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import models, security
from .database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nexus Docs")
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


class CreateDocRequest(BaseModel):
    title: str
    content: str = ""


class SaveVersionRequest(BaseModel):
    content: str


@app.get("/documents")
def list_documents(claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    docs = (
        db.query(models.Document)
        .filter_by(org_id=claims.org_id)
        .order_by(models.Document.updated_at.desc())
        .all()
    )
    return [
        {"id": d.id, "title": d.title, "updated_at": d.updated_at.isoformat(), "created_by": d.created_by_email}
        for d in docs
    ]


@app.post("/documents")
def create_document(payload: CreateDocRequest, claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    doc = models.Document(org_id=claims.org_id, title=payload.title, created_by_email=claims.email)
    db.add(doc)
    db.flush()

    version = models.DocumentVersion(
        document_id=doc.id, org_id=claims.org_id, version_number=1,
        content=payload.content, author_email=claims.email,
    )
    db.add(version)
    db.commit()
    return {"id": doc.id, "title": doc.title}


@app.get("/documents/{doc_id}")
def get_document(doc_id: str, claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter_by(id=doc_id, org_id=claims.org_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    latest = (
        db.query(models.DocumentVersion)
        .filter_by(document_id=doc_id)
        .order_by(models.DocumentVersion.version_number.desc())
        .first()
    )
    return {
        "id": doc.id, "title": doc.title, "content": latest.content if latest else "",
        "version_number": latest.version_number if latest else 0,
        "updated_at": doc.updated_at.isoformat(),
    }


@app.put("/documents/{doc_id}")
def save_version(doc_id: str, payload: SaveVersionRequest, claims: Claims = Depends(get_claims),
                  db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter_by(id=doc_id, org_id=claims.org_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    last = (
        db.query(models.DocumentVersion)
        .filter_by(document_id=doc_id)
        .order_by(models.DocumentVersion.version_number.desc())
        .first()
    )
    next_version = (last.version_number + 1) if last else 1

    version = models.DocumentVersion(
        document_id=doc_id, org_id=claims.org_id, version_number=next_version,
        content=payload.content, author_email=claims.email,
    )
    db.add(version)
    doc.updated_at = datetime.datetime.utcnow()
    db.commit()
    return {"version_number": next_version}


@app.get("/documents/{doc_id}/versions")
def list_versions(doc_id: str, claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter_by(id=doc_id, org_id=claims.org_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    versions = (
        db.query(models.DocumentVersion)
        .filter_by(document_id=doc_id)
        .order_by(models.DocumentVersion.version_number.desc())
        .all()
    )
    return [
        {"version_number": v.version_number, "author_email": v.author_email, "created_at": v.created_at.isoformat()}
        for v in versions
    ]


@app.get("/documents/{doc_id}/versions/{version_number}")
def get_version(doc_id: str, version_number: int, claims: Claims = Depends(get_claims),
                 db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter_by(id=doc_id, org_id=claims.org_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    version = db.query(models.DocumentVersion).filter_by(document_id=doc_id, version_number=version_number).first()
    if not version:
        raise HTTPException(404, "Version not found")
    return {"version_number": version.version_number, "content": version.content, "author_email": version.author_email}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
