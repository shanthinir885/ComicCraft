"""Thin, shared wrapper around the Google Generative AI SDK.

Keeping the SDK behind one module means model names, credentials and error
translation live in a single place and can be swapped without touching routes.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger("comiccraft.gemini")

_configured = False


class GeminiConfigurationError(RuntimeError):
    """Raised when Gemini credentials or the SDK are unavailable."""


class GeminiGenerationError(RuntimeError):
    """Raised when the Gemini API call itself fails."""


def _import_sdk():
    """Import google.generativeai lazily so the app starts without it installed."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise GeminiConfigurationError(
            "The google-generativeai package is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc
    return genai


def _configure():
    """Configure the SDK exactly once with the server-side API key."""
    global _configured
    genai = _import_sdk()
    if not settings.gemini_configured:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not set. Add it to your .env file before generating a comic."
        )
    if not _configured:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _configured = True
    return genai


def generate_text(
    prompt: str,
    model_name: str,
    *,
    temperature: Optional[float] = None,
    json_mode: bool = False,
) -> str:
    """Call a Gemini model and return the raw text response.

    Args:
        prompt: Fully rendered prompt string.
        model_name: Model identifier taken from configuration.
        temperature: Optional sampling temperature override.
        json_mode: Request an ``application/json`` response mime type.

    Returns:
        The model's raw text output.

    Raises:
        GeminiConfigurationError: Missing SDK or API key.
        GeminiGenerationError: API/transport failure or an empty response.
    """
    genai = _configure()

    generation_config: dict = {
        "temperature": settings.GEMINI_TEMPERATURE if temperature is None else temperature,
    }
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    try:
        model = genai.GenerativeModel(model_name, generation_config=generation_config)
        response = model.generate_content(
            prompt,
            request_options={"timeout": settings.GEMINI_TIMEOUT_SECONDS},
        )
    except Exception as exc:  # noqa: BLE001 - SDK raises many concrete types
        message = str(exc)
        logger.exception("Gemini call failed for model %s", model_name)
        lowered = message.lower()
        if "api key" in lowered or "permission" in lowered or "401" in lowered:
            raise GeminiConfigurationError(
                "Your Gemini API key was rejected. Please verify GEMINI_API_KEY."
            ) from exc
        if "not found" in lowered or "404" in lowered:
            raise GeminiConfigurationError(
                f"The configured model '{model_name}' is unavailable for this API key."
            ) from exc
        raise GeminiGenerationError("The Gemini service could not be reached.") from exc

    text = (getattr(response, "text", "") or "").strip()
    if not text:
        raise GeminiGenerationError("Gemini returned an empty response.")
    return text
