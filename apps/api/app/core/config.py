import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

_HERE = Path(__file__).resolve().parent
_STORAGE_DIR = (_HERE.parent / "storage").resolve()
_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = (_STORAGE_DIR / "careerradar.db").resolve()


class Settings(BaseModel):
    app_name: str = "CareerRadar AI Matching Engine"
    app_version: str = "0.1.0"
    default_language: str = "tr"
    semantic_model_name: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    database_url: str = f"sqlite:///{_DB_PATH}"
    storage_dir: str = str(_STORAGE_DIR)
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8501",
            "http://127.0.0.1:8501",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]
    )
    semantic_balance: float = Field(default=0.2, ge=0.0, le=0.5)
    prefilter_limit: int = Field(default=1000, ge=50, le=5000)
    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = Field(default=120, ge=15, le=1440)
    scheduler_max_jobs_per_run: int = Field(default=10, ge=1, le=50)
    api_key: str = Field(
        default_factory=lambda: os.getenv("API_KEY", ""),
        description="Boş string = auth kapat (test/dev). Production'da env üzerinden ayarlanmalı.",
    )
    encryption_key: str = Field(
        default_factory=lambda: os.getenv("ENCRYPTION_KEY", ""),
        description="Opsiyonel. SMTP_PASS gibi hassas env alanlarını decrypt eder. Boş ise dev/test için plaintext fallback.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
