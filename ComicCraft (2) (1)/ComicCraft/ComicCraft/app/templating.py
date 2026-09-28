"""Shared Jinja2 template environment."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.config import settings

templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))
templates.env.globals["app_name"] = settings.APP_NAME
templates.env.globals["current_year"] = 2026
