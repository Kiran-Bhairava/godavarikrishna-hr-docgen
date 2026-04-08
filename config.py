import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required env variable: {key}")
    return value

class Settings:
    DATABASE_URL: str = _require("DATABASE_URL")
    DATABASE_URL_SYNC: str = _require("DATABASE_URL_SYNC")
    SECRET_KEY: str = _require("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    APP_NAME: str = os.getenv("APP_NAME", "HR Document Management System")

settings = Settings()