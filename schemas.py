from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class RegisterAdminRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "recruiter"


class UpdateUserRequest(BaseModel):
    is_active: bool


# ── Document Types ────────────────────────────────────────────────────────────

class DocumentTypeOut(BaseModel):
    id: int
    code: str
    label: str
    schema_fields: list[dict]


# ── Documents ─────────────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    document_type_id: int
    candidate_name: str
    form_data: dict


class DocumentUpdate(BaseModel):
    candidate_name: Optional[str] = None
    form_data: Optional[dict] = None


class DocumentOut(BaseModel):
    id: UUID
    document_type_id: int
    document_type_label: str
    document_type_code: Optional[str] = None   # used by admin drawer for field grouping
    candidate_name: str
    status: str
    current_version: int
    form_data: dict
    created_by: UUID
    created_by_name: Optional[str] = None       # recruiter's full name for admin table
    pdf_path: Optional[str] = None
    admin_notes: Optional[str] = None           # latest admin comment
    created_at: datetime
    updated_at: datetime


# ── Approvals ─────────────────────────────────────────────────────────────────

class ApprovalAction(BaseModel):
    comments: Optional[str] = None


class ApprovalLogOut(BaseModel):
    id: int
    document_id: UUID
    reviewed_by: UUID
    action: str
    comments: Optional[str] = None
    created_at: datetime