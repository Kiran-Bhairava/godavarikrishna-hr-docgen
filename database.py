import asyncpg
from config import settings

# Global connection pool — initialized on startup, closed on shutdown
pool: asyncpg.Pool | None = None


async def init_db():
    global pool
    # Strip the SQLAlchemy dialect prefix — asyncpg needs plain postgresql://
    dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)


async def close_db():
    global pool
    if pool:
        await pool.close()


async def get_conn() -> asyncpg.Connection:
    """FastAPI dependency — yields a connection from the pool."""
    async with pool.acquire() as conn:
        yield conn