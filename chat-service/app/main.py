"""
Nexus Workspace — Chat service.

Trusts JWTs issued by identity-service. Never sees a password, never
stores a user record — it just checks "is this a valid token, and
what org/user does it belong to" on every REST call and every
WebSocket connection. Messages are scoped to org_id so one tenant can
never read another tenant's channels, even by guessing a channel id.
"""
import datetime
from typing import Dict, List

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import models, security
from .database import Base, SessionLocal, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nexus Chat")
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


class CreateChannelRequest(BaseModel):
    name: str


class SendMessageRequest(BaseModel):
    content: str


@app.get("/channels")
def list_channels(claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    channels = db.query(models.Channel).filter_by(org_id=claims.org_id).all()
    if not channels:
        general = models.Channel(org_id=claims.org_id, name="general", created_by_email=claims.email)
        db.add(general)
        db.commit()
        channels = [general]
    return [{"id": c.id, "name": c.name} for c in channels]


@app.post("/channels")
def create_channel(payload: CreateChannelRequest, claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    channel = models.Channel(org_id=claims.org_id, name=payload.name, created_by_email=claims.email)
    db.add(channel)
    db.commit()
    return {"id": channel.id, "name": channel.name}


@app.get("/channels/{channel_id}/messages")
def get_messages(channel_id: str, claims: Claims = Depends(get_claims), db: Session = Depends(get_db)):
    channel = db.query(models.Channel).filter_by(id=channel_id, org_id=claims.org_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    rows = (
        db.query(models.Message)
        .filter_by(channel_id=channel_id, org_id=claims.org_id)
        .order_by(models.Message.created_at.asc())
        .limit(500)
        .all()
    )
    return [
        {"id": r.id, "user_email": r.user_email, "content": r.content, "created_at": r.created_at.isoformat()}
        for r in rows
    ]


# --- WebSocket real-time delivery -------------------------------------------

class ConnectionManager:
    def __init__(self):
        # channel_id -> list of (websocket, org_id)
        self.active: Dict[str, List[WebSocket]] = {}

    async def connect(self, channel_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(channel_id, []).append(ws)

    def disconnect(self, channel_id: str, ws: WebSocket):
        if channel_id in self.active and ws in self.active[channel_id]:
            self.active[channel_id].remove(ws)

    async def broadcast(self, channel_id: str, payload: dict):
        for ws in list(self.active.get(channel_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                pass


manager = ConnectionManager()


@app.websocket("/ws/{channel_id}")
async def chat_ws(websocket: WebSocket, channel_id: str, token: str = Query(...)):
    try:
        payload = security.require_claims(token)
    except security.InvalidToken:
        await websocket.close(code=4401)
        return

    org_id = payload["org_id"]
    user_email = payload["email"]
    user_id = payload["sub"]

    db = SessionLocal()
    channel = db.query(models.Channel).filter_by(id=channel_id, org_id=org_id).first()
    if not channel:
        await websocket.close(code=4404)
        db.close()
        return

    await manager.connect(channel_id, websocket)
    await manager.broadcast(channel_id, {
        "type": "system", "content": f"{user_email} joined", "created_at": datetime.datetime.utcnow().isoformat(),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            msg = models.Message(
                channel_id=channel_id, org_id=org_id, user_id=user_id,
                user_email=user_email, content=raw,
            )
            db.add(msg)
            db.commit()
            await manager.broadcast(channel_id, {
                "type": "message", "user_email": user_email, "content": raw,
                "created_at": msg.created_at.isoformat(),
            })
    except WebSocketDisconnect:
        manager.disconnect(channel_id, websocket)
        await manager.broadcast(channel_id, {
            "type": "system", "content": f"{user_email} left", "created_at": datetime.datetime.utcnow().isoformat(),
        })
    finally:
        db.close()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
