"""Orchestrates the full comic pipeline: outline -> story -> images -> layout -> PDF."""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.config import settings
from app.services.exporters import PDFExportError, save_pdf
from app.services.gemini_client import GeminiConfigurationError, GeminiGenerationError
from app.services.gemini_flash import generate_outline
from app.services.gemini_pro import generate_story
from app.services.image_generator import ImageGenerationError
from app.services.layout_builder import build_comic_layout, generate_panel_images
from app.utils.helpers import sanitize_filename, static_url
from app.utils.validators import AIOutputError

logger = logging.getLogger("comiccraft.pipeline")


class ComicGenerationError(RuntimeError):
    """User-facing pipeline failure with a safe, friendly message."""

    def __init__(self, message: str, code: str = "generation_error") -> None:
        super().__init__(message)
        self.code = code


def create_comic(
    story_prompt: str,
    character_name: str,
    setting: str,
    tone: str,
    art_style: str,
    export_pdf: bool = True,
) -> Dict[str, Any]:
    """Run the end-to-end comic generation pipeline.

    Returns a dict matching the ``ComicResponse`` schema.

    Raises:
        ComicGenerationError: Any stage failure, already converted into a
            message that is safe to show a user.
    """
    if not settings.gemini_configured:
        raise ComicGenerationError(
            "ComicCraft is not configured yet. Add your GEMINI_API_KEY to the .env file and restart the server.",
            code="missing_api_key",
        )

    warnings: list[str] = []

    # --- Stage 1: outline ------------------------------------------------
    try:
        outline_result = generate_outline(story_prompt, character_name, setting, tone, art_style)
    except GeminiConfigurationError as exc:
        raise ComicGenerationError(str(exc), code="configuration_error") from exc
    except AIOutputError as exc:
        raise ComicGenerationError(str(exc), code="invalid_ai_output") from exc
    except GeminiGenerationError as exc:
        raise ComicGenerationError(
            "The story engine is not responding right now. Please try again in a moment.",
            code="ai_service_error",
        ) from exc

    title = outline_result["title"]
    panels = outline_result["panels"]
    appearance = outline_result.get("character_appearance", "")

    # --- Stage 2: story --------------------------------------------------
    try:
        story = generate_story(title, panels, character_name, setting, tone, art_style, appearance)
    except GeminiConfigurationError as exc:
        raise ComicGenerationError(str(exc), code="configuration_error") from exc
    except AIOutputError as exc:
        raise ComicGenerationError(str(exc), code="invalid_ai_output") from exc
    except GeminiGenerationError as exc:
        raise ComicGenerationError(
            "We created your storyline but the writing step failed. Please try again.",
            code="ai_service_error",
        ) from exc

    # --- Stage 3: illustrations ------------------------------------------
    try:
        image_results, image_warnings = generate_panel_images(
            panels, slug=sanitize_filename(title), art_style=art_style
        )
        warnings.extend(image_warnings)
    except ImageGenerationError as exc:
        raise ComicGenerationError(str(exc), code="image_error") from exc

    # --- Stage 4: layout --------------------------------------------------
    layout = build_comic_layout(panels, story, image_results)

    # --- Stage 5: PDF export ---------------------------------------------
    pdf_url = None
    if export_pdf:
        try:
            pdf_path = save_pdf(
                layout,
                title=title,
                metadata={
                    "character_name": character_name,
                    "setting": setting,
                    "tone": tone,
                    "art_style": art_style,
                },
            )
            pdf_url = static_url(pdf_path)
        except PDFExportError as exc:
            logger.warning("PDF export failed: %s", exc)
            warnings.append("Your comic was created, but the PDF export failed. You can retry the download.")

    return {
        "success": True,
        "title": title,
        "character_name": character_name,
        "setting": setting,
        "tone": tone,
        "art_style": art_style,
        "panels": layout,
        "pdf_url": pdf_url,
        "warnings": warnings,
    }
