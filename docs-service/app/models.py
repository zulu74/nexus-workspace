import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from .database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=gen_id)
    org_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    created_by_email = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(String, primary_key=True, default=gen_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    org_id = Column(String, nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    content = Column(String, nullable=False)
    author_email = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
