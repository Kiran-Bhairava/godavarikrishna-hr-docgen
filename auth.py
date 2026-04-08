from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
import asyncpg
from uuid import UUID

from database import get_conn
from schemas import LoginRequest, TokenResponse, UserOut
from auth_service import authenticate_user, create_access_token, decode_token, get_user_by_id, get_admin_count, create_user
from schemas import LoginRequest, TokenResponse, UserOut, RegisterAdminRequest, CreateUserRequest, UpdateUserRequest

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer()


# ── Shared dependency ─────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_conn),
) -> asyncpg.Record:
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await get_user_by_id(conn, user_id)
    if not user or not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


def require_role(*roles: str):
    async def _check(current_user: asyncpg.Record = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(roles)}",
            )
        return current_user
    return _check


# ── Register first admin ──────────────────────────────────────────────────────

@router.post("/register/admin", response_model=UserOut, status_code=201)
async def register_admin(body: RegisterAdminRequest, conn: asyncpg.Connection = Depends(get_conn)):
    count = await get_admin_count(conn)
    if count > 0:
        raise HTTPException(status_code=403, detail="Admin already exists")
    user = await create_user(conn, body.email, body.full_name, body.password, "admin")
    return UserOut(**dict(user), role="admin")


# ── Admin: create user ────────────────────────────────────────────────────────

@router.post("/users", response_model=UserOut, status_code=201)
async def create_recruiter(
    body: CreateUserRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(require_role("admin")),
):
    existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = await create_user(conn, body.email, body.full_name, body.password, body.role)
    return UserOut(**dict(user), role=body.role)


# ── Admin: list all users ─────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserOut])
async def list_users(
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(require_role("admin")),
):
    rows = await conn.fetch(
        """
        SELECT u.id, u.email, u.full_name, u.is_active, u.created_at, r.name AS role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        ORDER BY u.created_at DESC
        """
    )
    return [UserOut(**dict(r)) for r in rows]


# ── Admin: update user (activate/deactivate) ──────────────────────────────────

@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    body: UpdateUserRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    current_user: asyncpg.Record = Depends(require_role("admin")),
):
    if str(user_id) == str(current_user["id"]):
        raise HTTPException(status_code=400, detail="Cannot modify your own account")

    row = await conn.fetchrow(
        """
        UPDATE users SET is_active = $1
        WHERE id = $2
        RETURNING id, email, full_name, is_active, created_at
        """,
        body.is_active, user_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    role_row = await conn.fetchrow(
        "SELECT r.name AS role FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = $1",
        user_id
    )
    return UserOut(**dict(row), role=role_row["role"])


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, conn: asyncpg.Connection = Depends(get_conn)):
    user = await authenticate_user(conn, body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(user_id=str(user["id"]), role=user["role"])
    return TokenResponse(access_token=token)


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def me(current_user: asyncpg.Record = Depends(get_current_user)):
    return UserOut(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
    )