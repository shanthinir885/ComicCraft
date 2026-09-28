"""Combine outline, story and illustrations into the final comic layout."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.services.image_generator import ImageGenerationError, generate_image
from app.utils.helpers import sanitize_filename, static_url

logger = logging.getLogger("comiccraft.layout")


def build_comic_layout(
    outline: List[Dict[str, Any]],
    story: List[Dict[str, Any]],
    image_results: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Merge outline, story and image data into renderable panel dicts.

    Args:
        outline: Validated outline panels.
        story: Validated narration/caption/dialogue entries.
        image_results: Optional per-panel image info produced by
            :func:`generate_panel_images`.

    Returns:
        A list of panel dicts matching the ``ComicPanel`` schema.
    """
    story_by_number = {entry["panel_number"]: entry for entry in story}
    images_by_number = {entry["panel_number"]: entry for entry in (image_results or [])}

    layout: List[Dict[str, Any]] = []
    for index, panel in enumerate(outline, start=1):
        number = panel.get("panel_number", index)
        story_entry = story_by_number.get(number, {})
        image_entry = images_by_number.get(number, {})

        layout.append(
            {
                "panel_number": number,
                "title": panel.get("title") or f"Panel {number}",
                "scene_description": panel.get("scene_description", ""),
                "caption": story_entry.get("caption", ""),
                "narration": story_entry.get("narration", ""),
                "dialogue": list(story_entry.get("dialogue", [])),
                "image_prompt": panel.get("image_prompt", ""),
                "image_url": image_entry.get("image_url"),
                "image_path": image_entry.get("image_path"),
                "image_error": image_entry.get("image_error"),
            }
        )

    return layout


def generate_panel_images(
    outline: List[Dict[str, Any]],
    slug: str,
    art_style: str = "",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Generate one illustration per panel, tolerating per-panel failures.

    Returns:
        ``(image_results, warnings)`` where a failed panel carries ``image_error``.

    Raises:
        ImageGenerationError: Only when *every* panel fails, which indicates a
            configuration problem rather than a transient issue.
    """
    results: List[Dict[str, Any]] = []
    warnings: List[str] = []
    safe_slug = sanitize_filename(slug or "comic", max_length=32)

    for panel in outline:
        number = panel.get("panel_number", len(results) + 1)
        prompt = panel.get("image_prompt", "")
        if art_style:
            prompt = f"{prompt}, {art_style} style"

        try:
            path = generate_image(prompt, filename=f"{safe_slug}_panel_{number}")
            results.append(
                {
                    "panel_number": number,
                    "image_path": str(path),
                    "image_url": static_url(path),
                    "image_error": None,
                }
            )
        except ImageGenerationError as exc:
            logger.warning("Panel %s illustration failed: %s", number, exc)
            message = str(exc)
            warnings.append(f"Panel {number}: {message}")
            results.append(
                {
                    "panel_number": number,
                    "image_path": None,
                    "image_url": None,
                    "image_error": message,
                }
            )

    if results and all(entry["image_url"] is None for entry in results):
        raise ImageGenerationError(warnings[0] if warnings else "No panel illustrations could be created.")

    return results, warnings
