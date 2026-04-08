from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
import asyncpg

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Returns payload dict or raises JWTError."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ── DB queries ────────────────────────────────────────────────────────────────

async def get_user_by_email(conn: asyncpg.Connection, email: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT u.id, u.email, u.full_name, u.password_hash, u.is_active, r.name AS role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.email = $1
        """,
        email,
    )


async def get_user_by_id(conn: asyncpg.Connection, user_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT u.id, u.email, u.full_name, u.is_active, u.created_at, r.name AS role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = $1
        """,
        user_id,
    )


async def authenticate_user(conn: asyncpg.Connection, email: str, password: str) -> asyncpg.Record | None:
    """Returns user record if credentials valid, else None."""
    user = await get_user_by_email(conn, email)
    if not user:
        return None
    if not user["is_active"]:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user

async def get_admin_count(conn: asyncpg.Connection) -> int:
    row = await conn.fetchrow(
        "SELECT COUNT(*) as cnt FROM users u JOIN roles r ON r.id = u.role_id WHERE r.name = 'admin'"
    )
    return row["cnt"]


async def create_user(conn: asyncpg.Connection, email: str, full_name: str, password: str, role_name: str) -> asyncpg.Record:
    hashed = hash_password(password)
    return await conn.fetchrow(
        """
        INSERT INTO users (id, email, full_name, password_hash, role_id, is_active)
        VALUES (gen_random_uuid(), $1, $2, $3, (SELECT id FROM roles WHERE name = $4), true)
        RETURNING id, email, full_name, is_active, created_at
        """,
        email, full_name, hashed, role_name
    )