"""Central configuration for ComicCraft.

All secrets and model identifiers are read from environment variables so that
no model name or API key is ever hard-coded across the application.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR: Path = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    """Parse a truthy environment string into a bool."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    """Parse an integer environment string, falling back to a default."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _as_float(value: str | None, default: float) -> float:
    """Parse a float environment string, falling back to a default."""
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


class Settings:
    """Application settings resolved once at import time."""

    def __init__(self) -> None:
        # --- Application -------------------------------------------------
        self.APP_NAME: str = os.getenv("APP_NAME", "ComicCraft")
        self.APP_ENV: str = os.getenv("APP_ENV", "development")
        self.DEBUG: bool = _as_bool(os.getenv("DEBUG"), True)
        self.HOST: str = os.getenv("HOST", "127.0.0.1")
        self.PORT: int = _as_int(os.getenv("PORT"), 8000)

        # --- Paths -------------------------------------------------------
        self.BASE_DIR: Path = BASE_DIR
        self.TEMPLATES_DIR: Path = BASE_DIR / "templates"
        self.STATIC_DIR: Path = BASE_DIR / "static"
        self.PANELS_DIR: Path = self.STATIC_DIR / "panels"
        self.EXPORTS_DIR: Path = self.STATIC_DIR / "exports"
        self.FONTS_DIR: Path = self.STATIC_DIR / "fonts"

        # --- Gemini ------------------------------------------------------
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.GEMINI_OUTLINE_MODEL: str = os.getenv(
            "GEMINI_OUTLINE_MODEL", "models/gemini-1.5-flash"
        ).strip()
        self.GEMINI_STORY_MODEL: str = os.getenv(
            "GEMINI_STORY_MODEL", "models/gemini-1.5-pro"
        ).strip()
        self.GEMINI_TIMEOUT_SECONDS: int = _as_int(
            os.getenv("GEMINI_TIMEOUT_SECONDS"), 90
        )
        self.GEMINI_TEMPERATURE: float = _as_float(
            os.getenv("GEMINI_TEMPERATURE"), 0.9
        )

        # --- Image generation -------------------------------------------
        # "stable_diffusion" (local diffusers) | "huggingface_api" | "placeholder"
        self.IMAGE_PROVIDER: str = os.getenv(
            "IMAGE_PROVIDER", "stable_diffusion"
        ).strip().lower()
        self.IMAGE_MODEL: str = os.getenv(
            "IMAGE_MODEL", "runwayml/stable-diffusion-v1-5"
        ).strip()
        self.GEMINI_IMAGE_MODEL: str = os.getenv(
            "GEMINI_IMAGE_MODEL", "models/gemini-3.1-flash-image"
        ).strip()
        self.HF_API_KEY: str = os.getenv("HF_API_KEY", "").strip()
        self.IMAGE_WIDTH: int = _as_int(os.getenv("IMAGE_WIDTH"), 512)
        self.IMAGE_HEIGHT: int = _as_int(os.getenv("IMAGE_HEIGHT"), 512)
        self.IMAGE_STEPS: int = _as_int(os.getenv("IMAGE_STEPS"), 25)
        self.IMAGE_GUIDANCE_SCALE: float = _as_float(
            os.getenv("IMAGE_GUIDANCE_SCALE"), 7.5
        )
        self.IMAGE_DEVICE: str = os.getenv("IMAGE_DEVICE", "auto").strip().lower()

        # --- Generation rules -------------------------------------------
        self.PANEL_COUNT: int = _as_int(os.getenv("PANEL_COUNT"), 5)
        self.MAX_PROMPT_LENGTH: int = _as_int(os.getenv("MAX_PROMPT_LENGTH"), 1000)
        self.MAX_NAME_LENGTH: int = _as_int(os.getenv("MAX_NAME_LENGTH"), 60)

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create runtime directories that must exist before serving."""
        for directory in (
            self.STATIC_DIR,
            self.PANELS_DIR,
            self.EXPORTS_DIR,
            self.FONTS_DIR,
            self.STATIC_DIR / "images",
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def gemini_configured(self) -> bool:
        """True when a Gemini API key is present."""
        return bool(self.GEMINI_API_KEY)

    @property
    def image_configured(self) -> bool:
        """True when the selected image provider has what it needs."""
        if self.IMAGE_PROVIDER == "huggingface_api":
            return bool(self.HF_API_KEY)
        if self.IMAGE_PROVIDER == "gemini_image":
            return bool(self.GEMINI_API_KEY)
        return True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()


settings = get_settings()
