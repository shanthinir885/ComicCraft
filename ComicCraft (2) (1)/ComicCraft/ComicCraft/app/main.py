"""FastAPI application factory and global error handling for ComicCraft."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.routes import router
from app.templating import templates
from app.utils.helpers import configure_logging

configure_logging()
logger = logging.getLogger("comiccraft")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Log configuration state at boot so misconfiguration is obvious."""
    logger.info("%s starting in %s mode", settings.APP_NAME, settings.APP_ENV)
    if not settings.gemini_configured:
        logger.warning(
            "GEMINI_API_KEY is missing - comic generation will return a configuration error."
        )
    logger.info("Image provider: %s (%s)", settings.IMAGE_PROVIDER, settings.IMAGE_MODEL)
    yield
    logger.info("%s shutting down", settings.APP_NAME)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title="ComicCraft API",
        description=(
            "ComicCraft turns a story idea into a complete AI-generated comic: "
            "structured panel outline, narration and dialogue, panel illustrations "
            "and a downloadable PDF."
        ),
        version="1.0.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    application.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
    application.include_router(router)

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Render a friendly error page for browsers, JSON for API clients."""
        if request.url.path.startswith(("/generate-comic", "/test-image", "/health")):
            return JSONResponse(
                status_code=exc.status_code,
                content={"success": False, "error": str(exc.detail), "code": "http_error"},
            )
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "app_name": settings.APP_NAME,
                "status_code": exc.status_code,
                "message": str(exc.detail),
            },
            status_code=exc.status_code,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Return a compact, safe validation error payload."""
        fields = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
            fields.append({"field": location or "payload", "message": error.get("msg", "Invalid value")})
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": "Please check your input.", "code": "validation_error", "fields": fields},
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Log the technical detail server-side and show a safe message."""
        logger.exception("Unhandled error on %s", request.url.path)
        if request.url.path.startswith(("/generate-comic", "/test-image", "/health")):
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Unexpected server error.", "code": "server_error"},
            )
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "app_name": settings.APP_NAME,
                "status_code": 500,
                "message": "Something went wrong on our side. Please try again.",
            },
            status_code=500,
        )

    return application


app = create_app()


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> HTMLResponse:
    """Return an inline SVG favicon so browsers stop requesting a missing file."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#7C5CFF"/>'
        '<path d="M20 20h24v16H30l-6 8v-8h-4z" fill="#fff"/></svg>'
    )
    return HTMLResponse(content=svg, media_type="image/svg+xml")
