"""Validation and normalisation of AI output and user input."""

from __future__ import annotations

from typing import Any, Dict, List

from app.config import settings
from app.utils.helpers import truncate

REQUIRED_PANEL_KEYS = ("panel_number", "title", "scene_description", "image_prompt")

_ALIASES: Dict[str, str] = {
    "panel": "panel_number",
    "panelnumber": "panel_number",
    "number": "panel_number",
    "index": "panel_number",
    "panel_title": "title",
    "scene": "scene_description",
    "description": "scene_description",
    "scenedescription": "scene_description",
    "imageprompt": "image_prompt",
    "prompt": "image_prompt",
    "art_prompt": "image_prompt",
}


class AIOutputError(ValueError):
    """Raised when AI output cannot be normalised into a usable structure."""


def _normalize_keys(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map common key variants emitted by LLMs onto the canonical schema keys."""
    normalized: Dict[str, Any] = {}
    for key, value in raw.items():
        canonical = _ALIASES.get(str(key).strip().lower().replace(" ", "_"), str(key).strip().lower())
        normalized[canonical] = value
    return normalized


def normalize_outline(payload: Any, expected_panels: int | None = None) -> List[Dict[str, Any]]:
    """Validate and normalise the outline returned by the outline model.

    Accepts either a bare list of panels or ``{"panels": [...]}``.
    Raises :class:`AIOutputError` when the payload is unusable.
    """
    expected = expected_panels or settings.PANEL_COUNT

    if isinstance(payload, dict):
        for key in ("panels", "comic_panels", "outline", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break

    if not isinstance(payload, list) or not payload:
        raise AIOutputError("The outline model did not return a list of panels.")

    panels: List[Dict[str, Any]] = []
    for position, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise AIOutputError(f"Panel {position} is not a valid object.")

        data = _normalize_keys(item)

        try:
            panel_number = int(data.get("panel_number", position))
        except (TypeError, ValueError):
            panel_number = position

        title = str(data.get("title") or f"Panel {panel_number}").strip()
        scene = str(data.get("scene_description") or "").strip()
        image_prompt = str(data.get("image_prompt") or "").strip()

        if not scene:
            raise AIOutputError(f"Panel {panel_number} is missing a scene description.")
        if not image_prompt:
            image_prompt = scene

        panels.append(
            {
                "panel_number": panel_number,
                "title": truncate(title, 120),
                "scene_description": truncate(scene, 600),
                "image_prompt": truncate(image_prompt, 600),
            }
        )

    panels.sort(key=lambda panel: panel["panel_number"])
    panels = panels[:expected]
    for index, panel in enumerate(panels, start=1):
        panel["panel_number"] = index

    if len(panels) < 2:
        raise AIOutputError("The outline model returned too few usable panels.")

    return panels


def normalize_story(payload: Any, panel_count: int) -> List[Dict[str, Any]]:
    """Validate and normalise the narration/dialogue payload per panel."""
    if isinstance(payload, dict):
        for key in ("panels", "story", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break

    if not isinstance(payload, list) or not payload:
        raise AIOutputError("The story model did not return per-panel content.")

    story: List[Dict[str, Any]] = []
    for position, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise AIOutputError(f"Story entry {position} is not a valid object.")

        data = _normalize_keys(item)
        raw_dialogue = data.get("dialogue", [])

        if isinstance(raw_dialogue, str):
            lines = [line.strip() for line in raw_dialogue.splitlines() if line.strip()]
        elif isinstance(raw_dialogue, list):
            lines = []
            for entry in raw_dialogue:
                if isinstance(entry, dict):
                    speaker = str(entry.get("speaker") or entry.get("character") or "").strip()
                    line = str(entry.get("line") or entry.get("text") or "").strip()
                    lines.append(f"{speaker}: {line}" if speaker else line)
                elif entry:
                    lines.append(str(entry).strip())
        else:
            lines = []

        story.append(
            {
                "panel_number": position,
                "caption": truncate(str(data.get("caption") or "").strip(), 240),
                "narration": truncate(str(data.get("narration") or "").strip(), 900),
                "dialogue": [truncate(line, 240) for line in lines if line][:6],
            }
        )

    if len(story) < panel_count:
        last = story[-1] if story else {"caption": "", "narration": "", "dialogue": []}
        while len(story) < panel_count:
            story.append(
                {
                    "panel_number": len(story) + 1,
                    "caption": last.get("caption", ""),
                    "narration": last.get("narration", ""),
                    "dialogue": [],
                }
            )

    return story[:panel_count]


def clean_user_text(value: str, limit: int) -> str:
    """Collapse whitespace and enforce a hard length limit on user input."""
    cleaned = " ".join(str(value or "").split())
    return cleaned[:limit]
