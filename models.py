"""
SQLAlchemy table definitions — used ONLY by Alembic for migrations.
All runtime queries go through raw asyncpg (see services/).
"""
import uuid
from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime,
    ForeignKey, JSON, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)  # 'recruiter' | 'admin'


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(Text, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DocumentType(Base):
    __tablename__ = "document_types"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False, unique=True)       # 'offer_letter'
    label = Column(String(100), nullable=False)                  # 'Offer Letter'
    template_file = Column(String(255), nullable=False)          # 'offer_letter.html.j2'
    schema_fields = Column(JSON, nullable=False)                 # dynamic form definition
    is_active = Column(Boolean, default=True, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type_id = Column(Integer, ForeignKey("document_types.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    candidate_name = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False, default="draft")
    # status: draft | pending_approval | approved | rejected
    form_data = Column(JSON, nullable=False)
    current_version = Column(Integer, default=1, nullable=False)
    pdf_path = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    form_data = Column(JSON, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
    )


class ApprovalLog(Base):
    __tablename__ = "approval_logs"

    id = Column(Integer, primary_key=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(20), nullable=False)  # 'approved' | 'rejected'
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())