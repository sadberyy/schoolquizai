import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME: str = "Quiz Generator API"

    GIGACHAT_AUTH_KEY: str = os.getenv("GIGACHAT_AUTH_KEY", "")
    GIGACHAT_SCOPE: str = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    GIGACHAT_MODEL: str = os.getenv("GIGACHAT_MODEL", "GigaChat")
    GIGACHAT_CA_BUNDLE_FILE: str = os.getenv(
        "GIGACHAT_CA_BUNDLE_FILE",
        "./certs/russian_trusted_root_ca_pem.crt"
    )

    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    ACCESS_TOKEN_TTL_SECONDS: int = int(
        os.getenv("ACCESS_TOKEN_TTL_SECONDS", str(7 * 24 * 60 * 60))
    )

settings = Settings()