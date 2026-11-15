import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from .database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String, primary_key=True, default=gen_id)
    org_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    created_by_email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=gen_id)
    channel_id = Column(String, ForeignKey("channels.id"), nullable=False, index=True)
    org_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False)
    user_email = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
