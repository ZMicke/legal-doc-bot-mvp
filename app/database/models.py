from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.session import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, unique=True, index=True, nullable=False)
    original_filename = Column(String, nullable=False)
    saved_path = Column(String, nullable=False)
    extracted_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClaimRequest(Base):
    __tablename__ = "claim_requests"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, index=True, nullable=False)
    user_request = Column(Text, nullable=False)
    result_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    docx_path = Column(String, nullable=True)
    trace_json = Column(Text, nullable=True)
