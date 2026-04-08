from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
import asyncpg
import json
import os

from database import get_conn
from auth import get_current_user, require_role
from schemas import DocumentCreate, DocumentUpdate, DocumentOut, ApprovalAction
from pdf_service import generate_pdf

router = APIRouter(prefix="/documents", tags=["documents"])


# ── Helper ─────────────────────────────────────────────────────────────────────

def parse_doc(row: asyncpg.Record, document_type_label: str = None, document_type_code: str = None) -> DocumentOut:
    """Converts asyncpg row to DocumentOut, parsing form_data from JSON string if needed."""
    data = dict(row)
    data["form_data"] = json.loads(data["form_data"]) if isinstance(data["form_data"], str) else data["form_data"]
    if document_type_label is not None:
        data["document_type_label"] = document_type_label
    if document_type_code is not None:
        data["document_type_code"] = document_type_code
    # Ensure optional fields default cleanly
    data.setdefault("document_type_code", None)
    data.setdefault("created_by_name", None)
    data.setdefault("admin_notes", None)
    return DocumentOut(**data)


# ── Document Types ─────────────────────────────────────────────────────────────

@router.get("/types")
async def list_document_types(
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(get_current_user),
):
    rows = await conn.fetch(
        "SELECT id, code, label, schema_fields FROM document_types WHERE is_active = true ORDER BY label"
    )
    return [dict(r) for r in rows]


# ── Documents ──────────────────────────────────────────────────────────────────

@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(
    body: DocumentCreate,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(require_role("recruiter", "admin")),
):
    doc_type = await conn.fetchrow(
        "SELECT id, label, code FROM document_types WHERE id = $1 AND is_active = true",
        body.document_type_id
    )
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")

    # Start at version 0 - version 1 will be created on first submission
    row = await conn.fetchrow(
        """
        INSERT INTO documents (id, document_type_id, created_by, candidate_name, status, form_data, current_version)
        VALUES (gen_random_uuid(), $1, $2, $3, 'draft', $4, 0)
        RETURNING id, document_type_id, created_by, candidate_name, status, form_data,
                  current_version, pdf_path, created_at, updated_at, NULL AS admin_notes
        """,
        body.document_type_id, current_user["id"], body.candidate_name,
        json.dumps(body.form_data)
    )

    return parse_doc(row, doc_type["label"], doc_type["code"])


@router.get("")
async def list_documents(
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(get_current_user),
):
    if current_user["role"] == "admin":
        rows = await conn.fetch(
            """
            SELECT d.id, d.document_type_id, dt.label AS document_type_label, dt.code AS document_type_code,
                   d.candidate_name, d.status, d.form_data, d.current_version,
                   d.created_by, u.full_name AS created_by_name, d.pdf_path, d.created_at, d.updated_at,
                   (SELECT comments FROM approval_logs WHERE document_id = d.id ORDER BY created_at DESC LIMIT 1) AS admin_notes
            FROM documents d
            JOIN document_types dt ON dt.id = d.document_type_id
            JOIN users u ON u.id = d.created_by
            ORDER BY d.created_at DESC
            """
        )
    else:
        rows = await conn.fetch(
            """
            SELECT d.id, d.document_type_id, dt.label AS document_type_label, dt.code AS document_type_code,
                   d.candidate_name, d.status, d.form_data, d.current_version,
                   d.created_by, u.full_name AS created_by_name, d.pdf_path, d.created_at, d.updated_at,
                   (SELECT comments FROM approval_logs WHERE document_id = d.id ORDER BY created_at DESC LIMIT 1) AS admin_notes
            FROM documents d
            JOIN document_types dt ON dt.id = d.document_type_id
            JOIN users u ON u.id = d.created_by
            WHERE d.created_by = $1
            ORDER BY d.created_at DESC
            """,
            current_user["id"]
        )

    return [parse_doc(r) for r in rows]


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: str,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(get_current_user),
):
    row = await conn.fetchrow(
        """
        SELECT d.id, d.document_type_id, dt.label AS document_type_label, dt.code AS document_type_code,
               d.candidate_name, d.status, d.form_data, d.current_version,
               d.created_by, d.pdf_path, d.created_at, d.updated_at,
               (SELECT comments FROM approval_logs WHERE document_id = d.id ORDER BY created_at DESC LIMIT 1) AS admin_notes
        FROM documents d
        JOIN document_types dt ON dt.id = d.document_type_id
        WHERE d.id = $1
        """,
        doc_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user["role"] == "recruiter" and str(row["created_by"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    return parse_doc(row)


@router.put("/{doc_id}", response_model=DocumentOut)
async def update_document(
    doc_id: str,
    body: DocumentUpdate,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(require_role("recruiter", "admin")),
):
    doc = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft documents can be edited")
    if current_user["role"] == "recruiter" and str(doc["created_by"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    # Don't increment version when editing draft - version increments on submit
    new_form_data = json.dumps(body.form_data) if body.form_data else doc["form_data"]
    new_candidate = body.candidate_name or doc["candidate_name"]

    row = await conn.fetchrow(
        """
        UPDATE documents
        SET candidate_name = $1, form_data = $2, updated_at = now()
        WHERE id = $3
        RETURNING id, document_type_id, candidate_name, status, form_data,
                  current_version, created_by, pdf_path, created_at, updated_at,
                  (SELECT comments FROM approval_logs WHERE document_id = $3 ORDER BY created_at DESC LIMIT 1) AS admin_notes
        """,
        new_candidate, new_form_data, doc_id
    )

    doc_type = await conn.fetchrow(
        "SELECT label, code FROM document_types WHERE id = $1", 
        row["document_type_id"]
    )
    return parse_doc(row, doc_type["label"], doc_type["code"])


# ── Status Transitions ─────────────────────────────────────────────────────────

@router.post("/{doc_id}/submit", response_model=DocumentOut)
async def submit_document(
    doc_id: str,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(require_role("recruiter", "admin")),
):
    doc = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft documents can be submitted")
    if current_user["role"] == "recruiter" and str(doc["created_by"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    # Increment version and save snapshot when submitting
    new_version = doc["current_version"] + 1
    
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            UPDATE documents SET status = 'pending_approval', current_version = $1, updated_at = now()
            WHERE id = $2
            RETURNING id, document_type_id, candidate_name, status, form_data,
                      current_version, created_by, pdf_path, created_at, updated_at, NULL AS admin_notes
            """,
            new_version, doc_id
        )
        
        # Save version snapshot
        await conn.execute(
            """
            INSERT INTO document_versions (document_id, version_number, form_data, created_by)
            VALUES ($1, $2, $3, $4)
            """,
            doc_id, new_version, doc["form_data"], current_user["id"]
        )
    
    doc_type = await conn.fetchrow(
        "SELECT label, code FROM document_types WHERE id = $1", 
        row["document_type_id"]
    )
    return parse_doc(row, doc_type["label"], doc_type["code"])


@router.post("/{doc_id}/approve", response_model=DocumentOut)
async def approve_document(
    doc_id: str,
    body: ApprovalAction,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(require_role("admin")),
):
    doc = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["status"] != "pending_approval":
        raise HTTPException(status_code=400, detail="Document is not pending approval")

    # Fetch doc type code for dispatcher
    doc_type = await conn.fetchrow(
        "SELECT code, label FROM document_types WHERE id = $1",
        doc["document_type_id"]
    )
    if not doc_type:
        raise HTTPException(status_code=500, detail="Document type not found")

    form_data = json.loads(doc["form_data"]) if isinstance(doc["form_data"], str) else doc["form_data"]

    try:
        pdf_path = generate_pdf(
            document_id=str(doc["id"]),
            doc_type_code=doc_type["code"],
            form_data=form_data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    async with conn.transaction():
        row = await conn.fetchrow(
            """
            UPDATE documents SET status = 'approved', pdf_path = $1, updated_at = now()
            WHERE id = $2
            RETURNING id, document_type_id, candidate_name, status, form_data,
                      current_version, created_by, pdf_path, created_at, updated_at,
                      $3 AS admin_notes
            """,
            pdf_path, doc_id, body.comments
        )
        await conn.execute(
            """
            INSERT INTO approval_logs (document_id, reviewed_by, action, comments)
            VALUES ($1, $2, 'approved', $3)
            """,
            doc_id, current_user["id"], body.comments
        )

    return parse_doc(row, doc_type["label"], doc_type["code"])


@router.post("/{doc_id}/reject", response_model=DocumentOut)
async def reject_document(
    doc_id: str,
    body: ApprovalAction,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(require_role("admin")),
):
    doc = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["status"] != "pending_approval":
        raise HTTPException(status_code=400, detail="Document is not pending approval")

    async with conn.transaction():
        row = await conn.fetchrow(
            """
            UPDATE documents SET status = 'rejected', updated_at = now()
            WHERE id = $1
            RETURNING id, document_type_id, candidate_name, status, form_data,
                      current_version, created_by, pdf_path, created_at, updated_at,
                      $2 AS admin_notes
            """,
            doc_id, body.comments
        )
        await conn.execute(
            """
            INSERT INTO approval_logs (document_id, reviewed_by, action, comments)
            VALUES ($1, $2, 'rejected', $3)
            """,
            doc_id, current_user["id"], body.comments
        )

    doc_type = await conn.fetchrow(
        "SELECT label, code FROM document_types WHERE id = $1", 
        row["document_type_id"]
    )
    return parse_doc(row, doc_type["label"], doc_type["code"])


# ── PDF Download ───────────────────────────────────────────────────────────────

@router.get("/{doc_id}/approval-logs")
async def get_approval_logs(
    doc_id: str,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(get_current_user),
):
    """Get approval/rejection history with admin comments."""
    doc = await conn.fetchrow("SELECT id, created_by FROM documents WHERE id = $1", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if current_user["role"] == "recruiter" and str(doc["created_by"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    logs = await conn.fetch(
        """
        SELECT al.id, al.document_id, al.action, al.comments, al.created_at,
               u.full_name AS reviewer_name
        FROM approval_logs al
        JOIN users u ON u.id = al.reviewed_by
        WHERE al.document_id = $1
        ORDER BY al.created_at DESC
        """,
        doc_id
    )
    return [dict(log) for log in logs]


@router.post("/{doc_id}/revise", response_model=DocumentOut)
async def revise_document(
    doc_id: str,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(require_role("recruiter", "admin")),
):
    """Move rejected document back to draft for editing."""
    doc = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["status"] != "rejected":
        raise HTTPException(status_code=400, detail="Only rejected documents can be revised")
    if current_user["role"] == "recruiter" and str(doc["created_by"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    row = await conn.fetchrow(
        """
        UPDATE documents SET status = 'draft', updated_at = now()
        WHERE id = $1
        RETURNING id, document_type_id, candidate_name, status, form_data,
                  current_version, created_by, pdf_path, created_at, updated_at,
                  (SELECT comments FROM approval_logs WHERE document_id = $1 ORDER BY created_at DESC LIMIT 1) AS admin_notes
        """,
        doc_id
    )
    
    doc_type = await conn.fetchrow(
        "SELECT label, code FROM document_types WHERE id = $1", 
        row["document_type_id"]
    )
    return parse_doc(row, doc_type["label"], doc_type["code"])


@router.get("/{doc_id}/pdf")
async def download_pdf(
    doc_id: str,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(get_current_user),
):
    doc = await conn.fetchrow(
        "SELECT id, created_by, status, pdf_path, candidate_name FROM documents WHERE id = $1",
        doc_id
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user["role"] == "recruiter" and str(doc["created_by"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    if doc["status"] != "approved":
        raise HTTPException(status_code=400, detail="PDF is only available for approved documents")
    # /tmp is ephemeral on Vercel — regenerate if file missing
    pdf_path = doc["pdf_path"]
    if not pdf_path or not os.path.exists(pdf_path):
        doc_full = await conn.fetchrow(
            """
            SELECT d.*, dt.code AS doc_type_code
            FROM documents d
            JOIN document_types dt ON dt.id = d.document_type_id
            WHERE d.id = $1
            """,
            doc_id
        )
        if not doc_full:
            raise HTTPException(status_code=404, detail="PDF file not found")
        import json as _json
        form_data = _json.loads(doc_full["form_data"]) if isinstance(doc_full["form_data"], str) else doc_full["form_data"]
        try:
            pdf_path = generate_pdf(
                document_id=str(doc_full["id"]),
                doc_type_code=doc_full["doc_type_code"],
                form_data=form_data,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF regeneration failed: {str(e)}")

    filename = f"{doc['candidate_name'].replace(' ', '_')}.pdf"
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
    )