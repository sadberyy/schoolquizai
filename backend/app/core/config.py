import os
from dotenv import load_dotenv

load_dotenv()


def _parse_cors_origins() -> list[str]:
    """CORS_ORIGINS (через запятую) или один FRONTEND_ORIGIN; локально — localhost:5173."""
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
        if origins:
            return origins
    single = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").strip().rstrip("/")
    return [single or "http://localhost:5173"]


class Settings:
    APP_NAME: str = "Quiz Generator API"

    GIGACHAT_AUTH_KEY: str = os.getenv("GIGACHAT_AUTH_KEY", "")
    GIGACHAT_SCOPE: str = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    GIGACHAT_MODEL: str = os.getenv("GIGACHAT_MODEL", "GigaChat")
    GIGACHAT_CA_BUNDLE_FILE: str = os.getenv(
        "GIGACHAT_CA_BUNDLE_FILE",
        "./certs/russian_trusted_root_ca_pem.crt"
    )

    CORS_ORIGINS: list[str] = _parse_cors_origins()
    FRONTEND_ORIGIN: str = CORS_ORIGINS[0]
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    ACCESS_TOKEN_TTL_SECONDS: int = int(
        os.getenv("ACCESS_TOKEN_TTL_SECONDS", str(7 * 24 * 60 * 60))
    )

settings = Settings()