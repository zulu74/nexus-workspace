import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, String
from .database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Mail(Base):
    """
    Intra-org mail only — delivery is a row insert, not real SMTP/MX
    routing between domains. A real cross-domain mail system (DNS, MX
    records, SPF/DKIM/DMARC, spam filtering) is a genuinely different
    and much larger problem, called out as a real next step rather
    than faked here.
    """
    __tablename__ = "mail"

    id = Column(String, primary_key=True, default=gen_id)
    org_id = Column(String, nullable=False, index=True)
    from_email = Column(String, nullable=False)
    to_email = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    body = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
