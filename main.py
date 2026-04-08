from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from config import settings
from database import init_db, close_db
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from auth import router as auth_router
from documents import router as documents_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# API routes
app.include_router(auth_router)
app.include_router(documents_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}

# Redirect root to login
@app.get("/")
async def root():
    return RedirectResponse(url="/index.html")

# Mount static files (HTML, CSS, JS) - must be last
app.mount("/", StaticFiles(directory=".", html=True), name="static")