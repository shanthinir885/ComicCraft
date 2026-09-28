"""Story generation (Gemini Pro) — narration, captions and character dialogue."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.config import settings
from app.services.gemini_client import generate_text
from app.utils.helpers import extract_json
from app.utils.validators import AIOutputError, normalize_story

logger = logging.getLogger("comiccraft.story")

STORY_PROMPT_TEMPLATE = """You are an award-winning comic book writer.

Write the full script for a {panel_count}-panel comic titled "{title}".

MAIN CHARACTER: {character_name}
CHARACTER APPEARANCE: {character_appearance}
SETTING: {setting}
TONE: {tone}
ART STYLE: {art_style}

PANEL OUTLINE (JSON):
{outline_json}

Guidelines:
- Maintain continuity: {character_name}'s personality, voice and appearance stay identical across panels.
- "caption" is a short ambient caption box line (max 18 words).
- "narration" is 2-3 vivid sentences describing action and emotion.
- "dialogue" is a list of speech-bubble lines formatted exactly as "SPEAKER: line" (1-3 lines per panel).
- The {tone} tone must be felt in every panel. No markdown, no headings, no extra commentary.

Respond ONLY with valid JSON in exactly this shape:
{{
  "panels": [
    {{
      "panel_number": 1,
      "caption": "...",
      "narration": "...",
      "dialogue": ["{character_name}: ...", "VOICE: ..."]
    }}
  ]
}}
"""


def build_story_prompt(
    title: str,
    outline: List[Dict[str, Any]],
    character_name: str,
    character_appearance: str,
    setting: str,
    tone: str,
    art_style: str,
) -> str:
    """Render the story prompt from the validated outline."""
    return STORY_PROMPT_TEMPLATE.format(
        panel_count=len(outline),
        title=title,
        character_name=character_name,
        character_appearance=character_appearance or "as described in the story idea",
        setting=setting,
        tone=tone,
        art_style=art_style,
        outline_json=json.dumps(outline, indent=2, ensure_ascii=False),
    )


def generate_story(
    title: str,
    outline: List[Dict[str, Any]],
    character_name: str,
    setting: str,
    tone: str,
    art_style: str,
    character_appearance: str = "",
) -> List[Dict[str, Any]]:
    """Expand a panel outline into narration, captions and dialogue.

    Returns:
        A list of dicts: ``{"panel_number", "caption", "narration", "dialogue"}``.

    Raises:
        AIOutputError: The story response could not be parsed or validated.
    """
    prompt = build_story_prompt(
        title, outline, character_name, character_appearance, setting, tone, art_style
    )

    raw = generate_text(
        prompt, settings.GEMINI_STORY_MODEL, temperature=settings.GEMINI_TEMPERATURE, json_mode=True
    )
    payload = extract_json(raw)

    if payload is None:
        logger.error("Story JSON parsing failed. Raw response: %s", raw[:2000])
        raise AIOutputError("The AI wrote a story we could not read. Please try again.")

    return normalize_story(payload, len(outline))
