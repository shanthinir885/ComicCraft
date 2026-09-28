"""All ComicCraft HTTP routes: pages, form flow, JSON API and utilities."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import ValidationError

from app.config import settings
from app.schemas import (
    ALLOWED_ART_STYLES,
    ALLOWED_TONES,
    ComicResponse,
    ErrorResponse,
    HealthResponse,
    ImageTestRequest,
    PromptRequest,
    SUGGESTED_SETTINGS,
)
from app.services.comic_service import ComicGenerationError, create_comic
from app.services.image_generator import ImageGenerationError, generate_image
from app.templating import templates
from app.utils.helpers import ensure_within, static_url
from app.utils.validators import clean_user_text

logger = logging.getLogger("comiccraft.routes")

router = APIRouter()


def _form_context(request: Request, **extra) -> dict:
    """Shared Jinja2 context for pages that render the creation form."""
    context = {
        "request": request,
        "app_name": settings.APP_NAME,
        "tones": ALLOWED_TONES,
        "art_styles": ALLOWED_ART_STYLES,
        "settings_options": SUGGESTED_SETTINGS,
        "max_prompt_length": settings.MAX_PROMPT_LENGTH,
        "panel_count": settings.PANEL_COUNT,
        "gemini_configured": settings.gemini_configured,
        "image_provider": settings.IMAGE_PROVIDER,
    }
    context.update(extra)
    return context


@router.get("/", response_class=HTMLResponse, name="home", tags=["Pages"])
async def home(request: Request) -> HTMLResponse:
    """Render the landing page and comic creation workspace."""
    return templates.TemplateResponse(request, "index.html", _form_context(request))


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health() -> HealthResponse:
    """Lightweight health and configuration probe."""
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        environment=settings.APP_ENV,
        gemini_configured=settings.gemini_configured,
        image_provider=settings.IMAGE_PROVIDER,
        image_configured=settings.image_configured,
    )


@router.post("/generate", response_class=HTMLResponse, tags=["Comic"])
async def generate_comic_form(
    request: Request,
    story_prompt: str = Form(...),
    character_name: str = Form(...),
    setting: str = Form(...),
    tone: str = Form(...),
    art_style: str = Form(...),
) -> HTMLResponse:
    """Handle the browser form submission and render the comic preview page."""
    try:
        payload = PromptRequest(
            story_prompt=clean_user_text(story_prompt, settings.MAX_PROMPT_LENGTH),
            character_name=clean_user_text(character_name, settings.MAX_NAME_LENGTH),
            setting=clean_user_text(setting, settings.MAX_NAME_LENGTH),
            tone=clean_user_text(tone, settings.MAX_NAME_LENGTH),
            art_style=clean_user_text(art_style, settings.MAX_NAME_LENGTH),
        )
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "index.html",
            _form_context(
                request,
                error="Please complete every field before generating your comic.",
            ),
            status_code=422,
        )

    try:
        comic = create_comic(**payload.model_dump())
    except ComicGenerationError as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            _form_context(request, error=str(exc)),
            status_code=502,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected failure in form generation")
        return templates.TemplateResponse(
            request,
            "index.html",
            _form_context(request, error="Something went wrong while creating your comic. Please try again."),
            status_code=500,
        )

    return templates.TemplateResponse(
        request,
        "comic_preview.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "comic": comic,
            "layout": comic["panels"],
            "title": comic["title"],
            "pdf_url": comic["pdf_url"],
            "warnings": comic["warnings"],
        },
    )


@router.post(
    "/generate-comic/json",
    response_model=ComicResponse,
    responses={422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    tags=["Comic"],
)
async def generate_comic_json(payload: PromptRequest) -> JSONResponse:
    """Generate a comic from a raw JSON payload and return structured data."""
    try:
        comic = create_comic(**payload.model_dump())
    except ComicGenerationError as exc:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(error=str(exc), code=exc.code).model_dump(),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected failure in JSON generation")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Something went wrong while creating your comic.",
                code="server_error",
            ).model_dump(),
        )

    return JSONResponse(content=ComicResponse(**comic).model_dump())


@router.post("/test-image", tags=["Developer"])
async def test_image(payload: ImageTestRequest) -> JSONResponse:
    """Developer utility: generate a single illustration from a raw prompt."""
    try:
        path = generate_image(payload.prompt)
    except ImageGenerationError as exc:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(error=str(exc), code="image_error").model_dump(),
        )
    return JSONResponse(
        content={
            "success": True,
            "message": "Image generated successfully.",
            "image_url": static_url(path),
            "provider": settings.IMAGE_PROVIDER,
        }
    )


@router.get("/download", tags=["Comic"])
async def download_pdf(pdf_url: str, title: Optional[str] = None) -> FileResponse:
    """Serve an exported PDF as a download, guarding against path traversal."""
    relative = pdf_url.replace("/static/", "", 1).lstrip("/")
    candidate = settings.STATIC_DIR / relative
    try:
        safe_path = ensure_within(settings.EXPORTS_DIR, candidate)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid download request.")

    if not Path(safe_path).exists():
        raise HTTPException(status_code=404, detail="That comic export is no longer available.")

    filename = f"{(title or 'comiccraft-comic').strip()[:60]}.pdf".replace("/", "-")
    return FileResponse(path=str(safe_path), media_type="application/pdf", filename=filename)


@router.get("/export-success", response_class=HTMLResponse, name="export_success", tags=["Pages"])
async def export_success(
    request: Request,
    pdf_url: Optional[str] = None,
    title: Optional[str] = None,
) -> HTMLResponse:
    """Confirmation page shown after a successful PDF export."""
    return templates.TemplateResponse(
        request,
        "export_success.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "pdf_url": pdf_url,
            "title": title or "Your ComicCraft Comic",
        },
    )
