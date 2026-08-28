"""Metroika configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # API Configuration
    aicredits_api_key: str = "YOUR_API_KEY"
    aicredits_base_url: str = "https://aicredits.in/v1"
    vision_model: str = "moonshotai/kimi-k2.5"

    # Database
    database_url: str = "sqlite+aiosqlite:///./metroika.db"

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    report_dir: Path = Path(__file__).resolve().parent.parent / "reports"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.report_dir.mkdir(parents=True, exist_ok=True)
