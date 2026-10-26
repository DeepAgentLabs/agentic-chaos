from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Search for .env in current and parent directories
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env", override=False)
load_dotenv(override=False)


class Settings:
    ROOT_DIR: Path = _root
    ARTIFACTS_DIR: Path = _root / "artifacts"
    STORAGE_DB_PATH: Path = _root / "artifacts" / "finassure.sqlite"

    # Gemini AI configuration
    GEMINI_API_KEY: str = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()

    FLASH_MODEL: str = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    PRO_MODEL: str = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")

    # Server configuration
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "127.0.0.1")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    @classmethod
    def reload(cls) -> None:
        """Reload configuration from environment and .env."""
        load_dotenv(cls.ROOT_DIR / ".env", override=True)
        cls.GEMINI_API_KEY = (
            os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        ).strip()
        cls.FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
        cls.PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")

    @classmethod
    def has_gemini_key(cls) -> bool:
        return bool(cls.GEMINI_API_KEY and not cls.GEMINI_API_KEY.startswith("your_"))


settings = Settings()
settings.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
