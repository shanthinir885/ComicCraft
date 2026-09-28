"""Pydantic schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ComicPanel, ComicResponse, PromptRequest


def test_prompt_request_accepts_valid_payload() -> None:
    request = PromptRequest(
        story_prompt="  A brave fox   discovers a portal in an enchanted forest.  ",
        character_name=" Finn ",
        setting="Enchanted Forest",
        tone="Adventure",
        art_style="Comic Book",
    )
    assert request.character_name == "Finn"
    assert "  " not in request.story_prompt


def test_prompt_request_rejects_short_prompt() -> None:
    with pytest.raises(ValidationError):
        PromptRequest(
            story_prompt="short",
            character_name="Finn",
            setting="Space",
            tone="Epic",
            art_style="Anime",
        )


def test_prompt_request_rejects_blank_character() -> None:
    with pytest.raises(ValidationError):
        PromptRequest(
            story_prompt="A long enough story prompt for validation purposes.",
            character_name="   ",
            setting="Space",
            tone="Epic",
            art_style="Anime",
        )


def test_comic_response_serialises() -> None:
    response = ComicResponse(
        title="Finn and the Portal",
        character_name="Finn",
        setting="Enchanted Forest",
        tone="Adventure",
        art_style="Comic Book",
        panels=[
            ComicPanel(
                panel_number=1,
                title="The Forest's Edge",
                scene_description="Finn stands at the treeline.",
                caption="A hush falls.",
                narration="Finn steps forward.",
                dialogue=["FINN: Here we go."],
                image_prompt="A red fox at the edge of a forest",
            )
        ],
        pdf_url="/static/exports/comic.pdf",
    )
    payload = response.model_dump()
    assert payload["success"] is True
    assert payload["panels"][0]["panel_number"] == 1
