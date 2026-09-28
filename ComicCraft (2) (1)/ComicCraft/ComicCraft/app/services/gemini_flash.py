"""Outline generation (Gemini Flash) — structured 5-panel comic outlines."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.config import settings
from app.services.gemini_client import generate_text
from app.utils.helpers import extract_json
from app.utils.validators import AIOutputError, normalize_outline

logger = logging.getLogger("comiccraft.outline")

OUTLINE_PROMPT_TEMPLATE = """You are a professional AI comic planner.

Create a strictly formatted JSON outline for a {panel_count}-panel comic.

STORY IDEA: "{story_prompt}"
MAIN CHARACTER: {character_name}
SETTING: {setting}
TONE: {tone}
ART STYLE: {art_style}

Rules:
- Exactly {panel_count} panels with a clear beginning, rising action, turning point and resolution.
- {character_name} must appear consistently in every panel with the same described appearance.
- "image_prompt" must be a rich visual description in {art_style} style, mentioning {character_name}'s
  consistent look, the {setting} environment, lighting and camera framing. No text or speech bubbles
  in the image prompt.
- Keep every field concise and free of markdown.

Respond ONLY with valid JSON in exactly this shape:
{{
  "title": "Comic title here",
  "character_appearance": "One sentence describing the hero's consistent visual look",
  "panels": [
    {{
      "panel_number": 1,
      "title": "Panel title",
      "scene_description": "What happens in this panel",
      "image_prompt": "Detailed illustration prompt"
    }}
  ]
}}
"""


def build_outline_prompt(
    story_prompt: str,
    character_name: str,
    setting: str,
    tone: str,
    art_style: str,
    panel_count: int | None = None,
) -> str:
    """Render the outline prompt from user input."""
    return OUTLINE_PROMPT_TEMPLATE.format(
        panel_count=panel_count or settings.PANEL_COUNT,
        story_prompt=story_prompt,
        character_name=character_name,
        setting=setting,
        tone=tone,
        art_style=art_style,
    )


def generate_outline(
    story_prompt: str,
    character_name: str,
    setting: str,
    tone: str,
    art_style: str,
    panel_count: int | None = None,
) -> Dict[str, Any]:
    """Generate a validated comic outline.

    Returns:
        ``{"title": str, "character_appearance": str, "panels": [PanelOutline dicts]}``

    Raises:
        AIOutputError: The model response could not be parsed or validated.
        GeminiConfigurationError / GeminiGenerationError: Propagated from the client.
    """
    expected = panel_count or settings.PANEL_COUNT
    prompt = build_outline_prompt(
        story_prompt, character_name, setting, tone, art_style, expected
    )

    raw = generate_text(prompt, settings.GEMINI_OUTLINE_MODEL, temperature=0.8, json_mode=True)
    payload = extract_json(raw)

    if payload is None:
        logger.error("Outline JSON parsing failed. Raw response: %s", raw[:2000])
        raise AIOutputError("The AI returned an outline we could not read. Please try again.")

    title = ""
    appearance = ""
    if isinstance(payload, dict):
        title = str(payload.get("title") or "").strip()
        appearance = str(payload.get("character_appearance") or "").strip()

    panels: List[Dict[str, Any]] = normalize_outline(payload, expected)

    if not title:
        title = f"{character_name} and the {setting}"

    return {
        "title": title[:120],
        "character_appearance": appearance[:300],
        "panels": panels,
    }
